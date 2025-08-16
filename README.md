# LAN Chat v10 (Multi-Host + Multi-Room)

- **Multi-host**: Create multiple rooms from the same client (each on its own TCP port).
- **Discovery**: Multiple announcers run concurrently; UDP broadcast with socket reuse.
- **Dedupe**: by `room_id` with TTL cleanup (~6s). Creators don't see their own rooms.
- **Join flow**: after you join a room, it disappears from Available in that client.
- **Routing**: Active-room routing for sends; host broadcasts to all peers.
- **UI**: Available Rooms (manual Refresh), My Rooms (switch + auto Members tab), Members.

Run:
```bash
python -m lanchat.run
```
Allow local network access if your OS prompts.
