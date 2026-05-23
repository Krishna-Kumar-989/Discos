def serialize_message(msg):

    embeds = [
        e.to_dict()
        for e in msg.embeds
    ]

    attachments = []

    for a in msg.attachments:

        attachments.append({
            "filename": a.filename,
            "url": a.url,
            "size": a.size,
            "content_type": a.content_type
        })

    reactions = []

    for r in msg.reactions:

        reactions.append({
            "emoji": str(r.emoji),
            "count": r.count
        })

    reply_to = None

    if msg.reference:
        reply_to = str(
            msg.reference.message_id
        )

    return {
        "id": str(msg.id),

        "author": {
            "id": str(msg.author.id),
            "name": str(msg.author),
            "display_name": (
                msg.author.display_name
            ),
            "bot": msg.author.bot
        },

        "timestamp": (
            msg.created_at.isoformat()
        ),

        "edited_timestamp": (
            msg.edited_at.isoformat()
            if msg.edited_at else None
        ),

        "content": msg.content,

        "clean_content": (
            msg.clean_content
        ),

        "reply_to": reply_to,

        "attachments": attachments,

        "embeds": embeds,

        "reactions": reactions,

        "pinned": msg.pinned,

        "tts": msg.tts,

        "jump_url": msg.jump_url
    }