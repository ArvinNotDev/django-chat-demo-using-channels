import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from .models import User

class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract the room name from the URL
        self.user = self.scope["user"]
        self.room_name = self.scope["url_route"]["kwargs"]["room_name"]
        self.room_group_name = "chat_%s" % self.room_name

        # Check if user is authenticated
        if self.user.is_authenticated:
            # Join the room group
            await self.channel_layer.group_add(
                self.room_group_name,
                self.channel_name
            )

            # Accept the WebSocket connection
            await self.accept()

            # Update the user's online status and room
            await self.set_online(self.user.username)
            await self.set_room(self.user.username, self.room_name)

            # Get the current online users and send them
            online_users = await self.get_online_users(self.room_name)
            await self.send(text_data=json.dumps({
                "message": f"{self.user.username} has joined the room.",
                "online_users": online_users,
            }))
        else:
            # If not authenticated, send a message and close the connection
            await self.accept()
            await self.send(text_data=json.dumps({
                "message": "User is not authenticated!"
            }))
            await self.close(code=1000)

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        message = text_data_json['message']
        username = self.user.username

        # Get the current online users
        online_users = await self.get_online_users(self.room_name)

        # Send the message to the room group
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'chat_message',
                'message': message,
                'username': username,
                'online_users': online_users,
            }
        )

    async def chat_message(self, event):
        message = event['message']
        username = event['username']
        online_users = event['online_users']

        await self.send(text_data=json.dumps({
            'message': f"{username}: {message}",
            'online_users': online_users,
        }))

    async def disconnect(self, close_code):
        # Leave the room group and update user's online status
        await self.set_offline(self.user.username)
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )

    @database_sync_to_async
    def set_online(self, username):
        try:
            user_ = User.objects.get(username=username)
            user_.is_online = True
            user_.save()
        except User.DoesNotExist:
            print(f"User with username {username} does not exist.")

    @database_sync_to_async
    def set_offline(self, username):
        try:
            user_ = User.objects.get(username=username)
            user_.is_online = False
            user_.save()
        except User.DoesNotExist:
            print(f"User with username {username} does not exist.")

    @database_sync_to_async
    def set_room(self, username, room_name):
        try:
            user_ = User.objects.get(username=username)
            user_.which_room = room_name
            user_.save()
        except User.DoesNotExist:
            print(f"User with username {username} does not exist.")

    @database_sync_to_async
    def get_online_users(self, room_name):
        online_users = User.objects.filter(is_online=True, which_room=room_name)
        return [user.username for user in online_users]
