# -*- coding: utf-8 -*-
"""
main.py — AutoClipAI v7.2 — OPERATION PUBLICATION
"""
import os, json, time, sys, argparse, random, logging
from datetime import datetime
from dotenv import load_dotenv
from downloader import search_trending_videos, fill_stockpile
from publisher import publish_to_tiktok, publish_to_youtube_shorts
from memory import log_post
from strategy import get_active_queries
from cloud_storage import drive_manager
from omega_bypass import omega

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("AutoClipAI.Main")

PUBLISH_TO_TIKTOK = os.environ.get("PUBLISH_TO_TIKTOK", "true").lower() == "true"
PUBLISH_TO_YOUTUBE = os.environ.get("PUBLISH_TO_YOUTUBE", "true").lower() == "true"

def run_publication_mission():
    log.info("🚀 STARTING OPERATION PUBLICATION")
    for i in range(5):
        video_id, json_id, base_name = drive_manager.get_oldest_stockpile_video_and_metadata()
        if not video_id: break
        
        local_v, local_j = f"temp_{i}.mp4", f"temp_{i}.json"
        if drive_manager.download_file(video_id, local_v):
            meta = {"title": base_name}
            if json_id and drive_manager.download_file(json_id, local_j):
                with open(local_j, 'r') as f: meta = json.load(f)
            
            success = False
            if PUBLISH_TO_TIKTOK and publish_to_tiktok(local_v, meta):
                log_post(meta, "tiktok"); success = True
            if PUBLISH_TO_YOUTUBE and publish_to_youtube_shorts(local_v, meta):
                log_post(meta, "youtube"); success = True
            
            if success:
                drive_manager.delete_file(video_id)
                if json_id: drive_manager.delete_file(json_id)
            
            for f in [local_v, local_j]: 
                if os.path.exists(f): os.remove(f)
            time.sleep(random.randint(30, 60))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", type=str)
    args = parser.parse_args()
    omega.start_sidecar()
    try:
        if args.mode == "2" or args.mode == "5":
            run_publication_mission()
    finally:
        omega.stop_sidecar()

if __name__ == "__main__":
    main()
