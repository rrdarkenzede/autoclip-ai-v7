import os
from dotenv import load_dotenv

def display_status():
    print("-" * 60)
    print("   AUTOCLIP AI v7.0 -- PREPARATION CLOUD")
    print("-" * 60)
    
    # Check .env
    load_dotenv()
    gemini_key = os.getenv("GEMINI_API_KEY")
    
    print("\n[CONFIG] Verification du fichier .env :")
    if gemini_key:
        print(f"[OK] GEMINI_API_KEY : Trouvez ({gemini_key[:5]}...)")
    else:
        print("[ERROR] GEMINI_API_KEY : Absente ou vide.")
    
    print("\n" + "=" * 60)
    print("🚀 VOTRE PROJET EST PRET POUR LE CLOUD !")
    print("=" * 60)
    print("\nL'aspiration automatique des cookies a ete supprimee.")
    print("Veuillez suivre le guide manuel pour finaliser l'installation :")
    print("\n👉 FICHIER : cloud_setup_tutorial.md")
    print("=" * 60)

if __name__ == "__main__":
    display_status()
