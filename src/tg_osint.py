#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import sys
import re
import json
import getpass
import datetime as dt
from typing import Tuple, List, Dict, Any, Optional
from zoneinfo import ZoneInfo
from urllib.parse import urlparse

try:
    import colorama
    from colorama import Fore, Style
except ImportError:
    class Dummy: RESET_ALL = ""; RED = ""; CYAN = ""; YELLOW = ""; GREEN = ""
    colorama = None
    Fore = Style = Dummy()

from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError, FloodWaitError, RpcError
from telethon.errors.rpcerrorlist import (
    UsernameNotOccupiedError, UsernameInvalidError, ChannelPrivateError, ChatAdminRequiredError
)
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.contacts import ImportContactsRequest, DeleteContactsRequest
from telethon.tl.functions.users import GetFullUserRequest
from telethon.tl.types import (
    InputPhoneContact, InputUser,
    UserStatusEmpty, UserStatusOnline, UserStatusOffline, UserStatusRecently, UserStatusLastWeek, UserStatusLastMonth,
    MessageEntityTextUrl, MessageEntityUrl, MessageEntityMention, MessageEntityHashtag
)

def init_colorama(no_color: bool):
    if colorama and not no_color:
        colorama.init(autoreset=True)
    else:
        global Fore, Style
        class Dummy: RESET_ALL = ""; RED = ""; CYAN = ""; YELLOW = ""; GREEN = ""
        Fore = Style = Dummy()

def fmt_ts(dt_utc: Optional[dt.datetime], tzname: str) -> Optional[str]:
    if not dt_utc:
        return None
    if dt_utc.tzinfo is None:
        dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
    local = dt_utc.astimezone(ZoneInfo(tzname))
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")

URL_RE = re.compile(r'(https?://[^\s]+)', re.I)
AT_RE  = re.compile(r'@([A-Za-z0-9_]{5,})')
TAG_RE = re.compile(r'#(\w{2,})')

def extract_from_text(text: Optional[str]) -> Dict[str, List[str]]:
    if not text:
        return {"urls": [], "mentions": [], "hashtags": []}
    return {
        "urls": URL_RE.findall(text),
        "mentions": AT_RE.findall(text),
        "hashtags": TAG_RE.findall(text),
    }

def last_seen_str(status, tzname: str) -> str:
    if isinstance(status, UserStatusEmpty): return "never"
    if isinstance(status, UserStatusOnline): return "now"
    if isinstance(status, UserStatusOffline): return fmt_ts(status.was_online, tzname) or "unknown"
    if isinstance(status, UserStatusRecently): return "recently"
    if isinstance(status, UserStatusLastWeek): return "last week"
    if isinstance(status, UserStatusLastMonth): return "last month"
    return "unknown"

def safe_int(x) -> Optional[int]:
    try: return int(x)
    except Exception: return None

def collect_user_info(client: TelegramClient, entity, tz: str, photos: bool, limit_photos: int) -> Dict[str, Any]:
    full = client(GetFullUserRequest(entity))
    u = entity
    bio = getattr(full.full_user, "about", None)
    bio_entities = extract_from_text(bio)
    info = {
        "kind": "user",
        "id": u.id,
        "first_name": getattr(u, "first_name", None),
        "last_name": getattr(u, "last_name", None),
        "username": getattr(u, "username", None),
        "last_seen": last_seen_str(getattr(u, "status", None), tz),
        "bio": bio,
        "bio_urls": bio_entities["urls"],
        "bio_mentions": bio_entities["mentions"],
        "bio_hashtags": bio_entities["hashtags"],
        "premium": getattr(u, "premium", False),
        "verified": getattr(u, "verified", False),
        "bot": getattr(u, "bot", False),
        "scam": getattr(u, "scam", False),
        "fake": getattr(u, "fake", False),
        "support": getattr(u, "support", False),
        "bot_info_version": getattr(u, "bot_info_version", None),
        "restriction_reason": getattr(full.full_user, "restriction_reason", None),
        "emoji_status": bool(getattr(u, "emoji_status", None)),
        "emoji_status_until": getattr(getattr(u, "emoji_status", None), "until", None),
        "has_video_avatar": getattr(u, "video", False),
        "common_chats_count": getattr(full.full_user, "common_chats_count", None),
        "profile_photos_count": None,
        "downloaded_photos": [],
    }
    try:
        count = 0
        for _ in client.iter_profile_photos(u):
            count += 1
            if count >= 1_000_000: break
        info["profile_photos_count"] = count
    except RpcError:
        info["profile_photos_count"] = None
    if photos:
        try:
            path = f"{u.id}.jpg"
            p = client.download_profile_photo(u, file=path)
            if p: info["downloaded_photos"].append(p)
            i = 0
            for photo in client.iter_profile_photos(u):
                if limit_photos and i >= limit_photos: break
                date = getattr(photo, "date", None)
                date_str = date.strftime("%Y%m%d_%H%M%S") if date else f"photo_{i}"
                saved = client.download_media(photo, file=f"{date_str}.jpg")
                if saved: info["downloaded_photos"].append(saved)
                i += 1
        except FloodWaitError as e:
            info["download_error"] = f"Rate limited — wait {e.seconds}s"
        except RpcError as e:
            info["download_error"] = f"RPC error: {e.__class__.__name__}"
    return info

def collect_channel_info(client: TelegramClient, ch, tz: str, photos: bool, limit_photos: int) -> Dict[str, Any]:
    full = client(GetFullChannelRequest(ch))
    about = getattr(full.full_chat, "about", None)
    about_entities = extract_from_text(about)
    info = {
        "kind": "channel" if not ch.megagroup else "supergroup",
        "id": ch.id,
        "title": getattr(ch, "title", None),
        "username": getattr(ch, "username", None),
        "created": fmt_ts(getattr(ch, "date", None), tz),
        "about": about,
        "about_urls": about_entities["urls"],
        "about_mentions": about_entities["mentions"],
        "about_hashtags": about_entities["hashtags"],
        "megagroup": getattr(ch, "megagroup", False),
        "broadcast": getattr(ch, "broadcast", False),
        "forum": getattr(ch, "forum", False),
        "gigagroup": getattr(ch, "gigagroup", False),
        "verified": getattr(ch, "verified", False),
        "scam": getattr(ch, "scam", False),
        "fake": getattr(ch, "fake", False),
        "restricted": getattr(ch, "restricted", False),
        "participants_count": getattr(full.full_chat, "participants_count", None),
        "admins_count": getattr(full.full_chat, "admins_count", None),
        "kicked_count": getattr(full.full_chat, "kicked_count", None),
        "banned_count": getattr(full.full_chat, "banned_count", None),
        "online_count": getattr(full.full_chat, "online_count", None),
        "slowmode_seconds": getattr(full.full_chat, "slowmode_seconds", None),
        "default_banned_rights": getattr(full.full_chat, "default_banned_rights", None),
        "linked_chat_id": getattr(full.full_chat, "linked_chat_id", None),
        "stickerset": getattr(full.full_chat, "stickerset", None),
        "location": getattr(full.full_chat, "location", None),
        "theme_emoticon": getattr(ch, "theme_emoticon", None),
        "downloaded_photos": [],
    }
    if photos:
        try:
            path = f"{ch.id}.jpg"
            p = client.download_profile_photo(ch, file=path)
            if p: info["downloaded_photos"].append(p)
            i = 0
            for photo in client.iter_profile_photos(ch):
                if limit_photos and i >= limit_photos: break
                date = getattr(photo, "date", None)
                date_str = date.strftime("%Y%m%d_%H%M%S") if date else f"photo_{i}"
                saved = client.download_media(photo, file=f"{date_str}.jpg")
                if saved: info["downloaded_photos"].append(saved)
                i += 1
        except FloodWaitError as e:
            info["download_error"] = f"Rate limited — wait {e.seconds}s"
        except RpcError as e:
            info["download_error"] = f"RPC error: {e.__class__.__name__}"
    return info

def collect_group_info(client: TelegramClient, chat, tz: str, photos: bool, limit_photos: int) -> Dict[str, Any]:
    info = {
        "kind": "chat",
        "id": chat.id,
        "title": getattr(chat, "title", None),
        "created": fmt_ts(getattr(chat, "date", None), tz),
        "downloaded_photos": [],
    }
    if photos:
        try:
            p = client.download_media(getattr(chat, "photo", None), file=f"{chat.id}.jpg")
            if p: info["downloaded_photos"].append(p)
            i = 0
            for photo in client.iter_profile_photos(chat):
                if limit_photos and i >= limit_photos: break
                date = getattr(photo, "date", None)
                date_str = date.strftime("%Y%m%d_%H%M%S") if date else f"photo_{i}"
                saved = client.download_media(photo, file=f"{date_str}.jpg")
                if saved: info["downloaded_photos"].append(saved)
                i += 1
        except (FloodWaitError, RpcError) as e:
            info["download_error"] = str(e)
    return info

def collect_message_info(client: TelegramClient, url: str, tz: str) -> Dict[str, Any]:
    parsed = urlparse(url)
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) < 2:
        raise ValueError("Unsupported URL. Expected /<channel>/<message_id> or /c/<internal_id>/<message_id>")
    if parts[0] == "c":
        if len(parts) < 3: raise ValueError("Unsupported /c/ URL format.")
        entity_key = safe_int(parts[1])
        msg_id = safe_int(parts[2])
    else:
        entity_key = parts[0]
        msg_id = safe_int(parts[1])
    if msg_id is None: raise ValueError("Message id must be an integer.")
    entity = client.get_entity(entity_key)
    msg = client.get_messages(entity=entity, ids=msg_id)
    text = msg.text or msg.message or ""
    plain = extract_from_text(text or "")
    rich_urls, mentions, hashtags = [], [], []
    if msg.entities:
        for e in msg.entities:
            if isinstance(e, MessageEntityTextUrl): rich_urls.append(e.url)
            elif isinstance(e, MessageEntityMention):
                if text and e.offset is not None and e.length is not None:
                    mentions.append(text[e.offset:e.offset+e.length].lstrip("@"))
            elif isinstance(e, MessageEntityHashtag):
                if text and e.offset is not None and e.length is not None:
                    hashtags.append(text[e.offset:e.offset+e.length].lstrip("#"))
    media_info = None
    if msg.media:
        media_info = {"type": msg.media.__class__.__name__}
        if getattr(msg, "document", None):
            doc = msg.document
            media_info["mime_type"] = getattr(doc, "mime_type", None)
            media_info["size"] = getattr(doc, "size", None)
            name = None
            for a in getattr(doc, "attributes", []) or []:
                if hasattr(a, "file_name"): name = a.file_name; break
            media_info["file_name"] = name
        if getattr(msg, "photo", None):
            ph = msg.photo
            media_info["has_photo"] = True
    info = {
        "kind": "message",
        "channel": getattr(entity, "username", None) or getattr(entity, "id", None),
        "id": msg.id,
        "date": fmt_ts(getattr(msg, "date", None), tz),
        "edit_date": fmt_ts(getattr(msg, "edit_date", None), tz),
        "text": text,
        "views": getattr(msg, "views", None),
        "forwards": getattr(msg, "forwards", None),
        "replies": getattr(getattr(msg, "replies", None), "replies", None),
        "reactions": getattr(getattr(msg, "reactions", None), "results", None),
        "fwd_from": getattr(msg, "fwd_from", None),
        "via_bot_id": getattr(msg, "via_bot_id", None),
        "reply_to": getattr(msg, "reply_to", None),
        "entities_found": {
            "urls": sorted(set(plain["urls"] + rich_urls)),
            "mentions": sorted(set(plain["mentions"] + mentions)),
            "hashtags": sorted(set(plain["hashtags"] + hashtags)),
        },
        "media": media_info,
        "raw": msg.to_dict(),
    }
    return info

def cprint(label: str, value: Any):
    if value is None or value == "" or value == []: return
    print(f"{label}: {value}")

def print_user_human(info: Dict[str, Any]):
    cprint("User ID", info["id"])
    cprint("First name", info["first_name"])
    cprint("Last name", info["last_name"])
    cprint("Username", f"@{info['username']}" if info["username"] else None)
    cprint("Last seen", info["last_seen"])
    cprint("Flags", ", ".join([k for k in ["premium","verified","bot","scam","fake","support"] if info.get(k)]) or "none")
    cprint("Emoji status", "yes" if info["emoji_status"] else None)
    cprint("Emoji status until", info["emoji_status_until"])
    cprint("Bot info version", info["bot_info_version"])
    cprint("Restriction reason", info["restriction_reason"])
    cprint("Profile photos count", info["profile_photos_count"])
    if info.get("bio"):
        cprint("Bio", info["bio"])
        cprint("Bio URLs", ", ".join(info["bio_urls"]))
        cprint("Bio mentions", ", ".join(info["bio_mentions"]))
        cprint("Bio hashtags", ", ".join(info["bio_hashtags"]))
    if info.get("downloaded_photos"):
        cprint("Downloaded photos", ", ".join(info["downloaded_photos"]))

def print_channel_human(info: Dict[str, Any]):
    cprint("Type", info["kind"])
    cprint("Channel ID", info["id"])
    cprint("Title", info["title"])
    cprint("Username", f"@{info['username']}" if info["username"] else None)
    cprint("Created", info["created"])
    flags = [k for k in ["verified","scam","fake","restricted","forum","gigagroup","broadcast","megagroup"] if info.get(k)]
    cprint("Flags", ", ".join(flags) or "none")
    cprint("Participants", info["participants_count"])
    cprint("Admins", info["admins_count"])
    cprint("Online", info["online_count"])
    cprint("Banned", info["banned_count"])
    cprint("Kicked", info["kicked_count"])
    cprint("Slowmode (s)", info["slowmode_seconds"])
    cprint("Default banned rights", info["default_banned_rights"])
    cprint("Linked chat id", info["linked_chat_id"])
    cprint("Sticker set", info["stickerset"])
    cprint("Location", info["location"])
    cprint("Theme emoticon", info["theme_emoticon"])
    if info.get("about"):
        cprint("About", info["about"])
        cprint("About URLs", ", ".join(info["about_urls"]))
        cprint("About mentions", ", ".join(info["about_mentions"]))
        cprint("About hashtags", ", ".join(info["about_hashtags"]))
    if info.get("downloaded_photos"):
        cprint("Downloaded photos", ", ".join(info["downloaded_photos"]))

def print_chat_human(info: Dict[str, Any]):
    cprint("Type", info["kind"])
    cprint("Group ID", info["id"])
    cprint("Title", info["title"])
    cprint("Created", info["created"])
    if info.get("downloaded_photos"):
        cprint("Downloaded photos", ", ".join(info["downloaded_photos"]))

def print_message_human(info: Dict[str, Any]):
    cprint("Channel", info["channel"])
    cprint("Message ID", info["id"])
    cprint("Date", info["date"])
    cprint("Edited", info["edit_date"])
    cprint("Views", info["views"])
    cprint("Forwards", info["forwards"])
    cprint("Replies", info["replies"])
    cprint("Reactions", info["reactions"])
    cprint("Forwarded from", info["fwd_from"])
    cprint("Via bot id", info["via_bot_id"])
    cprint("Reply to", info["reply_to"])
    if info.get("text"): cprint("Text", info["text"])
    ents = info.get("entities_found", {})
    cprint("URLs", ", ".join(ents.get("urls", [])))
    cprint("Mentions", ", ".join(ents.get("mentions", [])))
    cprint("Hashtags", ", ".join(ents.get("hashtags", [])))
    if info.get("media"): cprint("Media", info["media"])

def main():
    parser = argparse.ArgumentParser(description="Telegram OSINT (public-access) — users/channels/groups/messages.")
    mx = parser.add_mutually_exclusive_group(required=True)
    mx.add_argument("-u", "--username", type=str, help="Username (with or without @)")
    mx.add_argument("-i", "--id", type=int, help="Numeric ID")
    mx.add_argument("-p", "--phone", type=str, help="Phone number with country code")
    mx.add_argument("-l", "--url", type=str, help="Public message URL (https://t.me/<channel>/<msg_id>)")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--photos", action="store_true", help="Download profile photos")
    parser.add_argument("--limit-photos", type=int, default=10, help="Max historical photos to download (default: 10)")
    parser.add_argument("--tz", default=os.getenv("TZ", "Europe/Paris"), help="Timezone for dates (default: Europe/Paris)")
    parser.add_argument("--session", default=os.getenv("TG_SESSION", "session_name"), help="Telethon session name")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")
    args = parser.parse_args()
    init_colorama(args.no_color)

    api_id = os.getenv("TG_API_ID")
    api_hash = os.getenv("TG_API_HASH")
    phone = os.getenv("TG_PHONE")
    if not api_id or not api_hash:
        print("Please set TG_API_ID and TG_API_HASH environment variables.", file=sys.stderr)
        sys.exit(1)
    api_id = int(api_id)

    client = TelegramClient(args.session, api_id, api_hash)
    try:
        client.start(phone=phone)
    except SessionPasswordNeededError:
        pwd = getpass.getpass("Enter 2FA password: ")
        client.sign_in(password=pwd)

    try:
        if args.username is not None:
            alias = args.username.lstrip("@")
            entity = client.get_entity(alias)
            etype = entity.__class__.__name__
            if etype == "User":
                info = collect_user_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_user_human(info)))
            elif etype == "Channel":
                info = collect_channel_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_channel_human(info)))
            else:
                info = collect_group_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_chat_human(info)))

        elif args.id is not None:
            entity = client.get_entity(args.id)
            etype = entity.__class__.__name__
            if etype == "User":
                info = collect_user_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_user_human(info)))
            elif etype == "Channel":
                info = collect_channel_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_channel_human(info)))
            else:
                info = collect_group_info(client, entity, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_chat_human(info)))

        elif args.phone is not None:
            phone_number = args.phone
            contact = InputPhoneContact(client_id=0, phone=phone_number, first_name="Temp", last_name="Contact")
            result = client(ImportContactsRequest([contact]))
            if result.users:
                user = result.users[0]
                info = collect_user_info(client, user, args.tz, args.photos, args.limit_photos)
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2) if args.json else (print_user_human(info)))
                client(DeleteContactsRequest(id=[InputUser(user_id=user.id, access_hash=user.access_hash)]))
            else:
                print(f"No user found with phone number {phone_number}")

        elif args.url is not None:
            info = collect_message_info(client, args.url, args.tz)
            if args.json:
                print(json.dumps(info, default=str, ensure_ascii=False, indent=2))
            else:
                info2 = {k: v for k, v in info.items() if k != "raw"}
                print_message_human(info2)

    except UsernameNotOccupiedError:
        print("Username not found."); sys.exit(2)
    except UsernameInvalidError:
        print("Invalid username."); sys.exit(2)
    except ChannelPrivateError:
        print("This chat/channel is private or requires membership."); sys.exit(3)
    except ChatAdminRequiredError:
        print("Admin rights required for this operation."); sys.exit(4)
    except FloodWaitError as e:
        print(f"Rate limited. Retry after {e.seconds}s."); sys.exit(5)
    except RpcError as e:
        print(f"Telegram RPC error: {e.__class__.__name__}: {e}"); sys.exit(6)
    except Exception as e:
        print(f"Unexpected error: {e}"); sys.exit(10)
    finally:
        client.disconnect()

if __name__ == "__main__":
    main()
