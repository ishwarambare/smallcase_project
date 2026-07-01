# stocks/consumers.py
"""
WebSocket consumers for real-time chat functionality using Django Channels.
This enables instant message delivery between users.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time chat messaging"""
    
    async def connect(self):
        """Handle WebSocket connection"""
        self.user = self.scope["user"]
        
        # Reject anonymous users
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Get group_id from URL route
        self.group_id = self.scope['url_route']['kwargs'].get('group_id')
        
        if self.group_id:
            self.room_group_name = f'chat_{self.group_id}'
        else:
            # Create a personal room for the user (for support chat)
            self.room_group_name = f'user_{self.user.id}'
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Send initial connection success message
        await self.send(text_data=json.dumps({
            'type': 'connection_established',
            'message': 'Connected to chat server',
            'room': self.room_group_name
        }))
    
    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type', 'message')
            
            if message_type == 'message':
                await self.handle_chat_message(data)
            elif message_type == 'join_group':
                await self.handle_join_group(data)
            elif message_type == 'typing':
                await self.handle_typing(data)
                
        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(e)
            }))
    
    async def handle_chat_message(self, data):
        """Handle sending a chat message"""
        content = data.get('content', '').strip()
        group_id = data.get('group_id') or self.group_id
        
        if not content:
            return
        
        # Save message to database
        message_data = await self.save_message(content, group_id)
        
        if message_data:
            # Broadcast to room group
            room_name = f'chat_{message_data["group_id"]}'
            
            await self.channel_layer.group_send(
                room_name,
                {
                    'type': 'chat_message',
                    'message': message_data
                }
            )
            
            # Also send to the sender's personal room for confirmation
            await self.send(text_data=json.dumps({
                'type': 'message_sent',
                'message': message_data
            }))
    
    async def handle_join_group(self, data):
        """Handle joining a different chat group"""
        new_group_id = data.get('group_id')
        
        if not new_group_id:
            return
        
        # Leave current group
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
        
        # Join new group
        self.group_id = new_group_id
        self.room_group_name = f'chat_{new_group_id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.send(text_data=json.dumps({
            'type': 'group_joined',
            'group_id': new_group_id,
            'room': self.room_group_name
        }))
    
    async def handle_typing(self, data):
        """Handle typing indicator"""
        group_id = data.get('group_id') or self.group_id
        is_typing = data.get('is_typing', False)
        
        if group_id:
            room_name = f'chat_{group_id}'
            await self.channel_layer.group_send(
                room_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'username': self.user.username or self.user.email.split('@')[0],
                    'is_typing': is_typing
                }
            )
    
    async def chat_message(self, event):
        """Handle chat message event from channel layer"""
        message = event['message'].copy()  # Copy to avoid mutating original
        
        # Set is_own based on whether this user is the sender
        message['is_own'] = message.get('sender_id') == self.user.id
        
        # Send to client
        await self.send(text_data=json.dumps({
            'type': 'new_message',
            'message': message
        }))
    
    async def typing_indicator(self, event):
        """Handle typing indicator event"""
        # Don't send typing indicator back to the typer
        if event['user_id'] != self.user.id:
            await self.send(text_data=json.dumps({
                'type': 'typing',
                'user_id': event['user_id'],
                'username': event['username'],
                'is_typing': event['is_typing']
            }))
    
    @database_sync_to_async
    def save_message(self, content, group_id):
        """Save message to database"""
        from .models import ChatGroup, ChatGroupMember, ChatMessage
        
        try:
            if group_id:
                group = ChatGroup.objects.get(id=group_id, is_active=True)
                # Verify user is member
                if not ChatGroupMember.objects.filter(
                    group=group, 
                    user=self.user, 
                    is_active=True
                ).exists():
                    return None
            else:
                # Get or create support chat
                membership = ChatGroupMember.objects.filter(
                    user=self.user,
                    group__group_type='support',
                    is_active=True
                ).select_related('group').first()
                
                if membership:
                    group = membership.group
                else:
                    # Create support chat
                    group = ChatGroup.objects.create(
                        name=f"Support Chat - {self.user.email}",
                        group_type='support',
                        created_by=self.user,
                        avatar='👨‍💻'
                    )
                    ChatGroupMember.objects.create(
                        group=group,
                        user=self.user,
                        role='member'
                    )
                    # Add welcome message
                    ChatMessage.objects.create(
                        group=group,
                        content="Hello! How can we help you today? 👋",
                        message_type='system'
                    )
            
            # Create message
            message = ChatMessage.objects.create(
                group=group,
                sender=self.user,
                content=content,
                message_type='text'
            )
            
            # Update group timestamp
            group.save()
            
            return {
                'id': message.id,
                'content': message.content,
                'sender': message.get_sender_name(),
                'sender_id': self.user.id,
                'message_type': message.message_type,
                'created_at': message.created_at.strftime('%H:%M'),
                'group_id': group.id,
                'is_own': True
            }
            
        except Exception as e:
            print(f"Error saving message: {e}")
            return None


class MarketDataConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time stock market tick data.

    Clients connect to:
        ws/market/              → subscribe to ALL symbols (global feed)
        ws/market/<SYMBOL>/     → subscribe to a specific symbol (e.g. RELIANCE)

    On connect: joins the appropriate Channel Layer group.
    On tick (from Fyers webhook via Channel Layer): forwards to browser.
    On connect: sends last known tick from DB (page-reload recovery).

    Message sent to browser:
        {
          "type": "tick",
          "symbol": "RELIANCE",
          "ltp": 2510.5,
          "open": 2490.0,
          "high": 2525.0,
          "low": 2485.0,
          "prev_close": 2505.0,
          "volume": 1245000,
          "change": 5.5,
          "change_pct": 0.2196,
          "source": "fyers",
          "timestamp": "2026-07-01T08:00:00Z"
        }
    """

    async def connect(self):
        """Handle WebSocket connection for market data."""
        # Symbol from URL route (None = subscribe to all)
        self.symbol = self.scope['url_route']['kwargs'].get('symbol', '').upper().strip()

        if self.symbol:
            # Symbol-specific group: market_RELIANCE, market_TCS, etc.
            self.group_name = f'market_{self.symbol}'
        else:
            # Global feed: all market ticks
            self.group_name = 'market_all'

        # Join channel layer group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Notify client of successful connection
        await self.send(text_data=json.dumps({
            'type': 'connected',
            'group': self.group_name,
            'symbol': self.symbol or 'ALL',
            'message': f'Subscribed to market feed: {self.group_name}',
        }))

        # Send last known tick(s) from DB for immediate display on page load
        await self.send_last_known_tick()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'group_name'):
            await self.channel_layer.group_discard(
                self.group_name,
                self.channel_name
            )

    async def receive(self, text_data):
        """
        Handle messages from the browser.
        Supports dynamic symbol subscription switching.
        """
        try:
            data = json.loads(text_data)
            msg_type = data.get('type', '')

            if msg_type == 'subscribe':
                # Browser requests to switch symbol
                new_symbol = data.get('symbol', '').upper().strip()
                await self.switch_symbol(new_symbol)

            elif msg_type == 'ping':
                await self.send(text_data=json.dumps({'type': 'pong'}))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': 'Invalid JSON'
            }))
        except Exception as exc:
            await self.send(text_data=json.dumps({
                'type': 'error',
                'message': str(exc)
            }))

    async def switch_symbol(self, new_symbol: str):
        """Allow browser to switch subscription to a different symbol."""
        # Leave current group
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

        # Update state
        self.symbol = new_symbol
        self.group_name = f'market_{new_symbol}' if new_symbol else 'market_all'

        # Join new group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.send(text_data=json.dumps({
            'type': 'subscribed',
            'symbol': self.symbol or 'ALL',
            'group': self.group_name,
        }))

        # Send last known tick for the new symbol
        await self.send_last_known_tick()

    async def market_tick(self, event):
        """
        Receive a market tick from the Channel Layer and forward to browser.
        This method is called by Django Channels when a group_send is done
        with type='market_tick'.
        """
        tick = event.get('tick', {})

        # Forward to browser WebSocket
        await self.send(text_data=json.dumps({
            'type': 'tick',
            **tick
        }))

    # ─────────────────────────────────────────────────────────────────────────
    # DB helpers
    # ─────────────────────────────────────────────────────────────────────────

    async def send_last_known_tick(self):
        """Fetch the last known tick(s) from DB and send to this client."""
        ticks = await self._get_last_ticks()
        if ticks:
            for tick_data in ticks:
                await self.send(text_data=json.dumps({
                    'type': 'last_tick',
                    **tick_data
                }))

    @database_sync_to_async
    def _get_last_ticks(self) -> list:
        """
        Fetch last known tick(s) from DB.
        - If symbol is set: return that symbol's tick
        - Otherwise: return last 20 ticks across all symbols
        """
        from .models import MarketTick
        try:
            if self.symbol:
                tick = MarketTick.objects.filter(symbol=self.symbol).first()
                return [tick.to_dict()] if tick else []
            else:
                ticks = MarketTick.objects.order_by('-timestamp')[:20]
                return [t.to_dict() for t in ticks]
        except Exception as exc:
            print(f"MarketDataConsumer: Error fetching last ticks: {exc}")
            return []

