from flask import Flask, request, jsonify, send_file
import os
import subprocess
import requests
from pathlib import Path
import uuid
import json

app = Flask(__name__)

# Configuration
TEMP_DIR = Path("/tmp/tiktok_videos")
TEMP_DIR.mkdir(exist_ok=True)

def download_file(url, filename):
    """Télécharge un fichier depuis une URL"""
    response = requests.get(url, stream=True)
    response.raise_for_status()
    
    with open(filename, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)
    
    return filename

def create_tiktok_video(youtube_url, satisfying_urls, output_path, duration=60):
    """
    Crée une vidéo TikTok avec :
    - Vidéo YouTube en haut (recadrée)
    - Vidéos satisfaisantes en bas
    Format vertical 9:16 (1080x1920)
    """
    
    job_id = str(uuid.uuid4())
    job_dir = TEMP_DIR / job_id
    job_dir.mkdir(exist_ok=True)
    
    # Télécharger la vidéo YouTube
    youtube_path = job_dir / "youtube.mp4"
    print(f"Téléchargement vidéo YouTube: {youtube_url}")
    download_file(youtube_url, youtube_path)
    
    # Télécharger les vidéos satisfaisantes
    satisfying_paths = []
    for i, url in enumerate(satisfying_urls):
        path = job_dir / f"satisfying_{i}.mp4"
        print(f"Téléchargement vidéo satisfaisante {i+1}: {url}")
        download_file(url, path)
        satisfying_paths.append(path)
    
    # Créer le filtre complexe FFmpeg
    # 1. Vidéo YouTube : crop et scale pour occuper le haut (1080x1280)
    # 2. Vidéos satisfaisantes : concaténer et loop pour occuper le bas (1080x640)
    
    # Préparer la concaténation des vidéos satisfaisantes
    concat_file = job_dir / "concat.txt"
    with open(concat_file, 'w') as f:
        for path in satisfying_paths:
            f.write(f"file '{path.absolute()}'\n")
    
    # Commande FFmpeg complexe
    filter_complex = (
        # Input 0: YouTube video - crop center et resize pour le haut
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,"
        "crop=1080:1280,setsar=1[youtube];"
        
        # Input 1: Vidéos satisfaisantes concaténées
        "[1:v]scale=1080:640:force_original_aspect_ratio=increase,"
        "crop=1080:640,setsar=1,loop=loop=-1:size=1:start=0[satisfying];"
        
        # Stack vertical: YouTube en haut, satisfying en bas
        "[youtube][satisfying]vstack=inputs=2[v]"
    )
    
    # Concaténer d'abord les vidéos satisfaisantes
    satisfying_concat_path = job_dir / "satisfying_concat.mp4"
    concat_cmd = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        str(satisfying_concat_path)
    ]
    
    print("Concaténation des vidéos satisfaisantes...")
    subprocess.run(concat_cmd, check=True, capture_output=True)
    
    # Créer la vidéo finale
    output = job_dir / "final.mp4"
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", str(youtube_path),
        "-stream_loop", "-1",  # Loop la vidéo satisfaisante
        "-i", str(satisfying_concat_path),
        "-filter_complex", filter_complex,
        "-map", "[v]",
        "-map", "0:a?",  # Garder l'audio de YouTube si disponible
        "-t", str(duration),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-r", "30",
        str(output)
    ]
    
    print("Création de la vidéo finale...")
    result = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"Erreur FFmpeg: {result.stderr}")
        raise Exception(f"Erreur lors de la création de la vidéo: {result.stderr}")
    
    return output

@app.route('/health', methods=['GET'])
def health():
    """Endpoint de santé"""
    return jsonify({"status": "ok", "service": "tiktok-video-creator"})

@app.route('/create-video', methods=['POST'])
def create_video():
    """
    Endpoint pour créer une vidéo TikTok
    
    Body JSON:
    {
        "youtube_url": "https://...",
        "satisfying_urls": ["https://...", "https://..."],
        "duration": 60
    }
    """
    try:
        data = request.json
        
        youtube_url = data.get('youtube_url')
        satisfying_urls = data.get('satisfying_urls', [])
        duration = data.get('duration', 60)
        
        if not youtube_url:
            return jsonify({"error": "youtube_url est requis"}), 400
        
        if not satisfying_urls or len(satisfying_urls) == 0:
            return jsonify({"error": "Au moins une satisfying_url est requise"}), 400
        
        # Créer la vidéo
        output_path = create_tiktok_video(
            youtube_url, 
            satisfying_urls, 
            None,
            duration
        )
        
        # Retourner la vidéo
        return send_file(
            output_path,
            mimetype='video/mp4',
            as_attachment=True,
            download_name='tiktok_video.mp4'
        )
        
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/create-video-url', methods=['POST'])
def create_video_url():
    """
    Endpoint pour créer une vidéo et retourner l'URL
    (À utiliser avec un stockage cloud)
    """
    try:
        data = request.json
        
        youtube_url = data.get('youtube_url')
        satisfying_urls = data.get('satisfying_urls', [])
        duration = data.get('duration', 60)
        
        if not youtube_url:
            return jsonify({"error": "youtube_url est requis"}), 400
        
        if not satisfying_urls or len(satisfying_urls) == 0:
            return jsonify({"error": "Au moins une satisfying_url est requise"}), 400
        
        # Créer la vidéo
        output_path = create_tiktok_video(
            youtube_url, 
            satisfying_urls, 
            None,
            duration
        )
        
        # Dans un vrai cas, tu uploaderas sur S3/GCS et retourneras l'URL
        return jsonify({
            "success": True,
            "video_path": str(output_path),
            "message": "Vidéo créée avec succès. Utilise /create-video pour télécharger directement."
        })
        
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Service de création vidéo TikTok démarré")
    print("📹 Endpoints disponibles:")
    print("   - POST /create-video : Créer et télécharger une vidéo")
    print("   - POST /create-video-url : Créer une vidéo et obtenir le path")
    print("   - GET /health : Vérifier le statut du service")
    app.run(host='0.0.0.0', port=5000, debug=True)
