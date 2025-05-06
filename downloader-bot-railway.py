from pyrogram import Client, filters
import yt_dlp
import os
import random
import string
import re
import hashlib
import datetime
import subprocess  # Untuk menjalankan FFMPEG
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Ganti dengan informasi bot kamu
API_ID = 28485220  
API_HASH = "b627630bddab42ee1d12c420d59e5b27"  
BOT_TOKEN = "8047420078:AAFHQwDKoxTZZPbJNkBh9jn0r-0e4WYEEJ4"

# Inisialisasi bot
bot = Client("video_downloader", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Batas maksimal ukuran file (MB)
MAX_FILE_SIZE_MB = 50  
HASH_DATABASE = "video_hashes.txt"

def generate_unique_filename():
    """Buat nama file unik dengan 40 karakter acak."""
    random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=40))
    return f"downloads/{random_string}.mp4"

def check_file_size_before_download(url):
    """Cek ukuran file sebelum download dimulai."""
    ydl_opts = {
        "quiet": True,
        "noplaylist": True,
        "skip_download": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            file_size_bytes = info.get("filesize") or info.get("filesize_approx")
            if file_size_bytes:
                return file_size_bytes / (1024 * 1024)  # Konversi ke MB
    except Exception as e:
        print(f"⚠️ Gagal mendapatkan ukuran file: {e}")
    return None

def get_video_hash(file_path):
    """Menghasilkan hash SHA-256 dari file video."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()

def is_duplicate(file_path):
    """Cek apakah hash video sudah ada di database."""
    file_hash = get_video_hash(file_path)

    if os.path.exists(HASH_DATABASE):
        with open(HASH_DATABASE, "r") as f:
            known_hashes = f.read().splitlines()

        if file_hash in known_hashes:
            return True  # Video sudah pernah diunduh

    # Jika belum ada, simpan hash-nya
    with open(HASH_DATABASE, "a") as f:
        f.write(file_hash + "\n")

    return False

def download_video(url):
    """Fungsi untuk mendownload video dari Xiaohongshu, Douyin, atau Rednote."""
    output_file = generate_unique_filename()
    ydl_opts = {
        "outtmpl": output_file,
        "format": "bv*[height<=1080]+ba/best",
        "merge_output_format": "mp4",
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_file  

def get_video_codec(file_path):
    """Mengecek codec video menggunakan FFMPEG."""
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=codec_name", "-of", "csv=p=0", file_path],
            capture_output=True,
            text=True
        )
        return result.stdout.strip()
    except Exception as e:
        print(f"⚠️ Gagal mendapatkan codec video: {e}")
        return None

def convert_to_h264(input_file):
    """Konversi video ke H.264 jika codec bukan H.264."""
    output_file = input_file.replace(".mp4", "_h264.mp4")
    try:
        subprocess.run(
            ["ffmpeg", "-i", input_file, "-c:v", "libx264", "-c:a", "aac", "-strict", "experimental", output_file, "-y"],
            check=True
        )
        return output_file
    except Exception as e:
        print(f"⚠️ Gagal mengonversi video: {e}")
        return None

@bot.on_message(filters.command(["start"]))
def start(client, message):
    """Handler untuk perintah /start."""
    message.reply_text("Kirim link video dari Rednote, Xiaohongshu, atau Douyin untuk di-download.")

@bot.on_message(filters.text & filters.private)
def download_handler(client, message):
    """Handler untuk menangani link yang dikirim oleh user dan mendeteksi ukuran sebelum download."""
    text = message.text.strip()

    # DEBUG: Print pesan yang diterima
    print("==== DEBUG INFO ====")
    print("Received message text:", text)
    print("Lowercased text:", text.lower())
    print("Check 'teks china' in text.lower():", "teks china" in text.lower())

    # Cek apakah ada kode "Teks China" (case-insensitive)
    need_blur = False
    if "teks china" in text.lower():
        need_blur = True
        print("need_blur set to True")
    else:
        print("need_blur remains False")
    print("==== END DEBUG INFO ====\n")

    # Ekstrak URL menggunakan regex
    url_pattern = re.search(r"https?://[^\s]+", text)
    if not url_pattern:
        msg = message.reply_text("Mohon kirimkan link yang valid dari Xiaohongshu, Douyin, atau Rednote.")
        client.delete_messages(chat_id=message.chat.id, message_ids=[msg.id], revoke=True)
        return

    url = url_pattern.group()  
    checking_msg = message.reply_text("🔍 Mengecek ukuran video...")

    try:
        # Ambil ukuran file sebelum download
        file_size_mb = check_file_size_before_download(url)
        if file_size_mb and file_size_mb > MAX_FILE_SIZE_MB:
            message.reply_text(f"❌ Video terlalu besar ({file_size_mb:.2f} MB). Maksimum adalah {MAX_FILE_SIZE_MB} MB.")
            client.delete_messages(chat_id=message.chat.id, message_ids=[message.id, checking_msg.id], revoke=True)
            return

        # Jika ukuran aman, lanjutkan download
        downloading_msg = message.reply_text("📥 Downloading video...")

        video_path = download_video(url)

        # Cek apakah video duplikat
        is_dup = is_duplicate(video_path)

        # Mengecek codec video
        codec = get_video_codec(video_path)
        if codec and codec.lower() != "h264":
            converting_msg = message.reply_text("⚠️ Video menggunakan codec selain H.264. Mengonversi...")
            converted_video = convert_to_h264(video_path)
            if converted_video:
                os.remove(video_path)  # Hapus video asli jika konversi berhasil
                video_path = converted_video
            client.delete_messages(chat_id=message.chat.id, message_ids=[converting_msg.id], revoke=True)

        # Tentukan caption utama
        if is_dup:
            caption_text = "🚫 Video ini sudah pernah diunduh sebelumnya!"
        else:
            caption_text = "✅ Video berhasil diunduh!"

        # Jika terdeteksi "Teks China", tambahkan warning
        if need_blur:
            caption_text += "\n⚠️ Perlu proses blurring teks"

        # Kirim video dengan tombol "Origin URL"
        sent_msg = client.send_video(
            chat_id=message.chat.id,
            video=video_path,
            caption=caption_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("Origin URL", url=url)]]
            )
        )

        # Hapus file video setelah dikirim
        os.remove(video_path)

        # Hapus pesan input dan pesan "checking"/"downloading"
        client.delete_messages(
            chat_id=message.chat.id,
            message_ids=[message.id, checking_msg.id, downloading_msg.id],
            revoke=True
        )

    except Exception as e:
        message.reply_text(f"Error: {e}")
        print(f"❌ Error: {e}")

bot.run()
