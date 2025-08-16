import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
from typing import List, Dict, Any, Callable

class ChatView(ttk.Frame):
    def __init__(self, master,
                 on_send: Callable[[str], None],
                 on_create_room: Callable[[str, bool], None],
                 on_join_selected_room: Callable[[int, str], None],
                 on_switch_room: Callable[[int], None],
                 on_refresh_rooms: Callable[[], None]):
        super().__init__(master)
        self.on_send = on_send
        self.on_create_room = on_create_room
        self.on_join_selected_room = on_join_selected_room
        self.on_switch_room = on_switch_room
        self.on_refresh_rooms = on_refresh_rooms
        self._build()

    def _build(self):
        self.pack(fill='both', expand=True)
        top = ttk.Frame(self)
        top.pack(side='top', fill='x')
        self.room_label = ttk.Label(top, text='Room: (none)')
        self.room_label.pack(side='left', padx=6, pady=6)
        ttk.Button(top, text='Create', command=self._create_room).pack(side='right', padx=4)

        body = ttk.Panedwindow(self, orient='horizontal')
        body.pack(fill='both', expand=True)

        self.left_tabs = ttk.Notebook(body)

        # Available Rooms tab
        tab_rooms = ttk.Frame(self.left_tabs)
        header = ttk.Frame(tab_rooms); header.pack(fill='x')
        ttk.Label(header, text='Discovered on LAN').pack(side='left', padx=6, pady=6)
        ttk.Button(header, text='Refresh', command=self.on_refresh_rooms).pack(side='right', padx=6, pady=6)

        self.rooms = tk.Listbox(tab_rooms)
        self.rooms.pack(fill='both', expand=True, padx=6, pady=(0,6))
        ttk.Label(tab_rooms, text='Double-click to join').pack(anchor='w', padx=6, pady=(0,6))
        self.rooms.bind('<Double-1>', self._join_from_list)
        self.left_tabs.add(tab_rooms, text='Available Rooms')

        # Joined Rooms tab
        tab_joined = ttk.Frame(self.left_tabs)
        ttk.Label(tab_joined, text='Rooms you joined').pack(anchor='w', padx=6, pady=(6,2))
        self.joined = tk.Listbox(tab_joined)
        self.joined.pack(fill='both', expand=True, padx=6, pady=(0,6))
        ttk.Label(tab_joined, text='Double-click to switch').pack(anchor='w', padx=6, pady=(0,6))
        self.joined.bind('<Double-1>', self._switch_room)
        self.left_tabs.add(tab_joined, text='My Rooms')

        # Members tab
        tab_members = ttk.Frame(self.left_tabs)
        ttk.Label(tab_members, text='Members').pack(anchor='w', padx=6, pady=(6,2))
        self.members = tk.Listbox(tab_members)
        self.members.pack(fill='both', expand=True, padx=6, pady=(0,6))
        self.left_tabs.add(tab_members, text='Members')

        body.add(self.left_tabs, weight=1)

        # Chat area
        right = ttk.Frame(body)
        self.chat = tk.Text(right, state='disabled', wrap='word')
        self.chat.pack(fill='both', expand=True, padx=6, pady=6)
        entry_row = ttk.Frame(right)
        entry_row.pack(fill='x', padx=6, pady=(0,6))
        self.entry = ttk.Entry(entry_row)
        self.entry.pack(side='left', fill='x', expand=True)
        self.entry.bind('<Return>', lambda e: self._send())
        ttk.Button(entry_row, text='Send', command=self._send).pack(side='left', padx=6)
        body.add(right, weight=4)

    def _create_room(self):
        name = simpledialog.askstring('Create Room', 'Room name:')
        if not name:
            return
        enc = messagebox.askyesno('Encryption', 'Enable encryption? (coming soon)')
        self.on_create_room(name, enc)

    def _join_from_list(self, event=None):
        idxs = self.rooms.curselection()
        if not idxs:
            return
        idx = idxs[0]
        nick = simpledialog.askstring('Nickname', 'Enter your nickname:')
        if not nick:
            return
        self.on_join_selected_room(idx, nick)

    def _switch_room(self, event=None):
        idxs = self.joined.curselection()
        if not idxs:
            return
        self.on_switch_room(idxs[0])
        self.left_tabs.select(2)  # Members tab

    def set_available_rooms(self, rooms: List[Dict[str, Any]]):
        self.rooms.delete(0, 'end')
        for r in rooms:
            txt = f"{r['room']} @ {r.get('from_addr', r.get('host_ip','?'))}:{r['host_tcp_port']}"
            self.rooms.insert('end', txt)

    def set_joined_rooms(self, room_names: List[str]):
        self.joined.delete(0, 'end')
        for name in room_names:
            self.joined.insert('end', name)

    def add_message(self, line: str):
        self.chat.configure(state='normal')
        self.chat.insert('end', line + '\n')
        self.chat.see('end')
        self.chat.configure('disabled')

    def set_chat(self, lines: List[str]):
        self.chat.configure(state='normal')
        self.chat.delete('1.0', 'end')
        for line in lines:
            self.chat.insert('end', line + '\n')
        self.chat.see('end')
        self.chat.configure(state='disabled')

    def set_room_title(self, title: str):
        self.room_label.configure(text=f"Room: {title}")

    def set_members(self, members: List[Dict[str, Any]]):
        self.members.delete(0, 'end')
        for m in members:
            self.members.insert('end', m.get('nick', m.get('peer_id', '')))

    def _send(self):
        text = self.entry.get().strip()
        if text:
            self.on_send(text)
            self.entry.delete(0, 'end')
