# stocks/management/commands/fyers_refresh_token.py
"""
Django management command to silently refresh the Fyers access token.

Usage:
    python manage.py fyers_refresh_token

Schedule this daily (before 6:30 AM IST) via:

Windows Task Scheduler:
    Action: python manage.py fyers_refresh_token
    Trigger: Daily at 6:00 AM

Linux/Mac cron (add to crontab -e):
    0 0 * * * cd /path/to/project && .venv/bin/python manage.py fyers_refresh_token

How it works:
    1. Reads FYERS_REFRESH_TOKEN + FYERS_PIN from .env
    2. POSTs to Fyers validate-refresh-token endpoint
    3. Writes the new FYERS_ACCESS_TOKEN back to .env automatically
    4. Re-initializes the FyersService singleton in-memory

Requirements:
    FYERS_REFRESH_TOKEN = <set automatically after first OAuth login>
    FYERS_PIN           = <your 4-digit Fyers trading PIN>

First login (one-time setup):
    python manage.py runserver
    GET http://localhost:8000/api/fyers/auth-url/
    → open URL in browser → login → copy auth_code
    POST http://localhost:8000/api/fyers/callback/ {"auth_code": "..."}
    → tokens saved to .env automatically

After the first login, this command handles everything daily.
"""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        'Silently refresh Fyers access token using the refresh token + PIN. '
        'No browser or manual login required. '
        'Schedule this daily (before 6:30 AM IST) via cron or Task Scheduler.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--pin',
            type=str,
            default='',
            help='4-digit Fyers trading PIN (overrides FYERS_PIN in .env)',
        )
        parser.add_argument(
            '--check-only',
            action='store_true',
            default=False,
            help='Only check if current token is valid; do not refresh.',
        )

    def handle(self, *args, **options):
        from stocks.fyers_service import fyers_service

        pin = options.get('pin', '').strip()
        check_only = options.get('check_only', False)

        self.stdout.write(self.style.HTTP_INFO(
            '\n══════════════════════════════════════════\n'
            '  Fyers Token Manager\n'
            '══════════════════════════════════════════'
        ))
        self.stdout.write(f'  client_id : {fyers_service.client_id or "(not set)"}')
        self.stdout.write(f'  has access_token  : {"Yes" if fyers_service.access_token else "No"}')
        self.stdout.write(f'  has refresh_token : {"Yes" if fyers_service.refresh_token else "No"}')
        self.stdout.write(f'  has PIN           : {"Yes" if (pin or fyers_service.pin) else "No"}')
        self.stdout.write('')

        if check_only:
            self.stdout.write('Mode: CHECK ONLY')
            is_valid = fyers_service.check_and_refresh()
            if is_valid:
                self.stdout.write(self.style.SUCCESS('✅ Token is valid.'))
            else:
                self.stdout.write(self.style.ERROR('❌ Token is invalid or expired.'))
                self.stdout.write(
                    self.style.WARNING(
                        'Run without --check-only to refresh, '
                        'or re-run OAuth flow if refresh token is expired.'
                    )
                )
            return

        # ── Refresh ───────────────────────────────────────────────────────────
        self.stdout.write('Mode: REFRESH ACCESS TOKEN')
        self.stdout.write('Calling Fyers validate-refresh-token endpoint…')

        result = fyers_service.refresh_access_token(pin=pin)

        if result['success']:
            token_preview = result['access_token'][:20] + '…' if result['access_token'] else '?'
            self.stdout.write(self.style.SUCCESS(
                f'\n✅ Success! New access token: {token_preview}\n'
                f'   Token written to .env as FYERS_ACCESS_TOKEN\n'
                f'   FyersService singleton re-initialized.\n'
            ))
        else:
            error = result.get('error', 'Unknown error')
            self.stderr.write(self.style.ERROR(
                f'\n❌ Token refresh failed:\n   {error}\n'
            ))

            # Hint: if refresh token expired, guide to re-login
            if 'expired' in error.lower() or 'invalid' in error.lower():
                self.stdout.write(self.style.WARNING(
                    '\n⚠️  Your refresh token has expired (15-day limit).\n'
                    '   Complete the OAuth login again:\n'
                    '   1. GET http://localhost:8000/api/fyers/auth-url/\n'
                    '   2. Open the returned URL in your browser\n'
                    '   3. Login to Fyers\n'
                    '   4. POST http://localhost:8000/api/fyers/callback/ '
                    '{"auth_code": "<code from redirect>"}\n'
                ))
            raise CommandError('Fyers token refresh failed.')
