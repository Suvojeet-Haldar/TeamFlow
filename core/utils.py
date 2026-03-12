from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

def broadcast_board_update(project_id, payload):
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f"project_{project_id}",
            {"type": "board_update", "data": payload}
        )
    except Exception:
        pass