#!/usr/bin/env python3
"""
Quick setup script for the Habit Tracker Discord Bot
"""

import os
import shutil

def main():
    print("🌱 Setting up your HabitualAI Discord Bot...")
    
    # Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        if os.path.exists('env.example'):
            shutil.copy('env.example', '.env')
            print("✅ Created .env file from template")
            print("📝 Please edit .env with your actual tokens and keys")
        else:
            print("❌ env.example not found")
    else:
        print("✅ .env file already exists")
    
    # Create bot directory if it doesn't exist
    if not os.path.exists('bot'):
        os.makedirs('bot')
        print("✅ Created bot directory")
    
    print("\n🚀 Next steps:")
    print("1. Edit .env with your Discord bot token")
    print("2. Add your Supabase URL and key (or set USE_LOCAL_ONLY=true)")
    print("3. Add your OpenAI API key for AI features")
    print("4. Run: pip install -r requirements.txt")
    print("5. Run: python bot/bot.py")
    print("\n🎉 Happy habit building!")

if __name__ == "__main__":
    main() 