"""Render and attach mobile-readable, verified Even/Odd monthly calendars."""
import calendar
import json
from datetime import date
from io import BytesIO
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

NAME = "statrally-evenodd-monthly-calendar.png"

def render_calendar(start, end, rows):
    from PIL import Image, ImageDraw, ImageFont

    first = start.replace(day=1)
    count = calendar.monthrange(first.year, first.month)[1]
    offset = (first.weekday() + 1) % 7
    weeks = (offset + count + 6) // 7
    width, margin, gap, cellheight = 980, 42, 9, 110
    cellwidth = (width - 2 * margin - 6 * gap) // 7
    height = 300 + weeks * cellheight + 115
    canvas = Image.new("RGB", (width, height), "#071527")
    pen = ImageDraw.Draw(canvas)
    def font(size, bold=False):
        try:
            path = "/usr/share/fonts/truetype/dejavu/DejaVuSans" + ("-Bold" if bold else "") + ".ttf"
            return ImageFont.truetype(path, size)
        except OSError:
            return ImageFont.load_default()
    white, muted = "#F3F7FD", "#A8BBD1"
    pen.text((margin, 29), "StatRally | Even/Odd Monthly Accuracy", font=font(32, True), fill=white)
    pen.text((margin, 79), f"{first:%B %Y} | Verified soccer + NHL results", font=font(22), fill=muted)

    all_graded = [r for r in rows if r["correct"] is not None and r["day"].year == first.year and r["day"].month == first.month and r["day"] <= end]
    wins = sum(r["correct"] is True for r in all_graded)
    score = f"{wins / len(all_graded):.1%}" if all_graded else "N/A"
    pen.text((margin, 130), score, font=font(58, True), fill=white)
    pen.text((360, 161), f"{wins}/{len(all_graded)} correct  |  Combined sports", font=font(22), fill=muted)
    top = 263
    for col, name in enumerate(("SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT")):
        pen.text((margin + col * (cellwidth + gap) + 9, 219), name, font=font(19, True), fill=muted)

    for number in range(1, count + 1):
        current = date(first.year, first.month, number)
        matches = [r for r in rows if r["day"] == current and r["correct"] is not None and current <= end]
        good = sum(r["correct"] is True for r in matches)
        total = len(matches)
        xidx = offset + number - 1
        col, row = xidx % 7, xidx // 7
        x, y = margin + col * (cellwidth + gap), top + row * cellheight
        color = ("#0D784A" if good / total >= .7 else "#9B2945") if total else "#26354A"
        pen.rounded_rectangle((x,y,x+cellwidth,y+cellheight-7), radius=12, fill=color)
        pen.text((x+9,y+6), str(number), font=font(19,True), fill=white)
        if total:
            pen.text((x+9,y+34), f"{good/total:.0%}", font=font(24,True), fill=white)
            pen.text((x+9,y+72), f"{good}/{total}", font=font(17), fill=white)
        else:
            pen.text((x+9,y+55), "—", font=font(22), fill=muted)
    bottom = top + weeks * cellheight + 17
    for x, color, label in ((margin,"#0D784A","70%+ accuracy"),(340,"#9B2945","Below 70%"),(615,"#26354A","No graded data")):
        pen.rounded_rectangle((x,bottom,x+24,bottom+24),radius=5,fill=color)
        pen.text((x+32,bottom-3),label,font=font(18),fill=muted)
    pen.text((margin,bottom+43),"Each date shows correct / graded. Accuracy is not model probability.",font=font(17),fill=muted)
    output=BytesIO()
    canvas.save(output,format="PNG",optimize=True)
    return output.getvalue()

def upload_image(webhook, message, png, message_id=None):
    """Send/edit the same Discord message with a PNG and a confirmed response."""
    parts = urlsplit(webhook)
    if (parts.scheme != "https" or parts.hostname not in ("discord.com","discordapp.com")
        or not parts.path.startswith("/api/webhooks/") or parts.username or parts.password):
        raise ValueError("Validated Discord webhook required")
    if message_id is not None and (not isinstance(message_id,str) or not message_id.isdigit()):
        raise ValueError("Confirmed Discord message ID required")
    base = parts._replace(query="",fragment="").geturl().rstrip("/")
    target = base + ("/messages/" + message_id if message_id else "?wait=true")
    method = "PATCH" if message_id else "POST"
    # Discord multipart requires payload_json and files[0]; preserve receipt on edits.
    import uuid
    boundary = "statrally" + uuid.uuid4().hex
    payload = dict(message)
    payload["attachments"] = [{"id":0,"filename":NAME,"description":"Even/Odd monthly accuracy calendar"}]
    if not isinstance(payload.get("embeds"),list) or len(payload["embeds"])!=1:
        raise ValueError("Expected one monthly recap embed")
    payload["embeds"][0]["image"] = {"url":"attachment://"+NAME}
    def part(name, body, mime, filename=None):
        header = f"--{boundary}\r\nContent-Disposition: form-data; name=\"{name}\""
        if filename:
            header += f"; filename=\"{filename}\""
        header += f"\r\nContent-Type: {mime}\r\n\r\n"
        return header.encode()+body+b"\r\n"
    body = (part("payload_json",json.dumps(payload).encode("utf-8"),"application/json")
            +part("files[0]",png,"image/png",NAME)
            +f"--{boundary}--\r\n".encode())
    request=Request(target,data=body,method=method,
                    headers={"Content-Type":"multipart/form-data; boundary="+boundary,
                             "User-Agent":"StatRally/0.1"})
    with urlopen(request,timeout=30) as response:
        if response.status!=200:
            raise RuntimeError("Discord calendar post/edit not confirmed")
        receipt=json.load(response)
    actual=str(receipt.get("id",""))
    if not actual.isdigit() or (message_id is not None and actual!=message_id):
        raise RuntimeError("Discord calendar message receipt invalid")
    return actual
