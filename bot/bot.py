import os
import asyncio
from datetime import datetime, date, time, timedelta
from typing import Optional
import discord
from discord.ext import commands, tasks
from dotenv import load_dotenv
import openai
from supabase import create_client, Client
import json
import pytz

# Load environment variables
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE')
USE_LOCAL_ONLY = os.getenv('USE_LOCAL_ONLY', 'false').lower() == 'true'

# Initialize Supabase client
supabase: Client = None
if not USE_LOCAL_ONLY and SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = False  # Don't need member info
intents.presences = False  # Don't need presence info
bot = commands.Bot(command_prefix='!', intents=intents)

# Dr. K-style system prompt
DR_K_SYSTEM_PROMPT = """You are a compassionate but realistic habit coach inspired by Dr. K from HealthyGamerGG. 

Your tone is:
- Encouraging but never toxic positivity
- Honest about struggles without being harsh
- Validating of human imperfection
- Focused on progress, not perfection
- Uses "look" and "here's the thing" naturally
- Acknowledges that building habits is genuinely hard

Avoid:
- Generic motivational quotes
- Shame or judgment for missed days
- Unrealistic expectations
- Corporate wellness speak

Keep responses concise (2-3 sentences max) and conversational."""

class HabitTracker:
    def __init__(self):
        self.local_file = 'checkins.json'
        
    async def get_or_create_user(self, discord_id: str, username: str) -> dict:
        """Get user from database or create if doesn't exist"""
        if USE_LOCAL_ONLY:
            return {'id': discord_id, 'discord_id': discord_id, 'discord_username': username}
            
        try:
            # Try to get existing user
            result = supabase.table('users').select('*').eq('discord_id', discord_id).execute()
            
            if result.data:
                return result.data[0]
            else:
                # Create new user - use service role for RLS bypass
                new_user = {
                    'discord_id': discord_id,
                    'discord_username': username
                }
                # Use rpc call to bypass RLS for user creation
                result = supabase.rpc('create_user_if_not_exists', {
                    'p_discord_id': discord_id,
                    'p_discord_username': username
                }).execute()
                
                if result.data:
                    return result.data[0] if isinstance(result.data, list) else result.data
                else:
                    # Fallback: try direct insert
                    result = supabase.table('users').insert(new_user).execute()
                    return result.data[0]
                
        except Exception as e:
            print(f"Database error: {e}")
            # Fallback to local mode for this user
            return {'id': discord_id, 'discord_id': discord_id, 'discord_username': username}
    
    async def add_checkin(self, user_id: str, discord_id: str, message: str = None, mood: int = None) -> dict:
        """Add a checkin for today - returns dict with success status and existing checkin info"""
        # Get user's timezone to determine their "today"
        user_today = await self._get_user_date(discord_id)
        
        if USE_LOCAL_ONLY:
            return self._add_local_checkin(discord_id, user_today, message, mood)
        
        try:
            # First check if checkin already exists for today (in user's timezone)
            existing_result = supabase.table('checkins').select('*').eq('user_id', user_id).eq('date', user_today.isoformat()).execute()
            
            if existing_result.data:
                # Return existing checkin info for confirmation
                existing = existing_result.data[0]
                return {
                    'success': False,
                    'existing': existing,
                    'new_message': message,
                    'new_mood': mood
                }
            
            # Use RPC function for checkin creation to handle RLS properly
            result = supabase.rpc('create_or_update_checkin', {
                'p_user_discord_id': discord_id,
                'p_date': user_today.isoformat(),
                'p_message': message,
                'p_mood': mood
            }).execute()
            
            return {'success': result.data is not None, 'existing': None}
            
        except Exception as e:
            print(f"Database error: {e}")
            return self._add_local_checkin(discord_id, user_today, message, mood)
    
    async def _get_user_date(self, discord_id: str) -> date:
        """Get the current date in the user's timezone"""
        try:
            if not USE_LOCAL_ONLY and supabase:
                # Get user's timezone from database
                result = supabase.table('users').select('timezone').eq('discord_id', discord_id).execute()
                if result.data and result.data[0].get('timezone'):
                    user_tz = pytz.timezone(result.data[0]['timezone'])
                    return datetime.now(user_tz).date()
            
            # Default to UTC if no timezone is set or in local mode
            return date.today()
            
        except Exception as e:
            print(f"Error getting user timezone: {e}")
            return date.today()
    
    def _add_local_checkin(self, discord_id: str, date_obj: date, message: str, mood: int) -> dict:
        """Add checkin to local JSON file - returns dict with success status and existing checkin info"""
        try:
            # Load existing data
            if os.path.exists(self.local_file):
                with open(self.local_file, 'r') as f:
                    data = json.load(f)
            else:
                data = {}
            
            # Initialize user data if needed
            if discord_id not in data:
                data[discord_id] = []
            
            # Check if checkin already exists for today
            date_str = date_obj.isoformat()
            existing = next((c for c in data[discord_id] if c['date'] == date_str), None)
            
            if existing:
                # Return existing checkin info for confirmation
                return {
                    'success': False,
                    'existing': existing,
                    'new_message': message,
                    'new_mood': mood
                }
            else:
                # Add new checkin
                checkin = {
                    'date': date_str,
                    'message': message,
                    'mood': mood,
                    'created_at': datetime.now().isoformat()
                }
                data[discord_id].append(checkin)
                
                # Save back to file
                with open(self.local_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return {'success': True, 'existing': None}
            
        except Exception as e:
            print(f"Local storage error: {e}")
            return {'success': False, 'existing': None}
    
    async def update_checkin(self, user_id: str, discord_id: str, message: str = None, mood: int = None) -> bool:
        """Force update today's checkin (after confirmation)"""
        # Get user's timezone to determine their "today"
        user_today = await self._get_user_date(discord_id)
        
        if USE_LOCAL_ONLY:
            return self._update_local_checkin(discord_id, user_today, message, mood)
        
        try:
            # Use RPC function to update checkin
            result = supabase.rpc('create_or_update_checkin', {
                'p_user_discord_id': discord_id,
                'p_date': user_today.isoformat(),
                'p_message': message,
                'p_mood': mood
            }).execute()
            
            return result.data is not None
            
        except Exception as e:
            print(f"Database error: {e}")
            return self._update_local_checkin(discord_id, user_today, message, mood)
    
    def _update_local_checkin(self, discord_id: str, date_obj: date, message: str, mood: int) -> bool:
        """Force update checkin in local JSON file"""
        try:
            # Load existing data
            if os.path.exists(self.local_file):
                with open(self.local_file, 'r') as f:
                    data = json.load(f)
            else:
                return False
            
            if discord_id not in data:
                return False
            
            # Find and update existing checkin
            date_str = date_obj.isoformat()
            for checkin in data[discord_id]:
                if checkin['date'] == date_str:
                    checkin['message'] = message
                    checkin['mood'] = mood
                    checkin['updated_at'] = datetime.now().isoformat()
                    break
            
            # Save back to file
            with open(self.local_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            return True
            
        except Exception as e:
            print(f"Local storage error: {e}")
            return False
    
    async def get_user_stats(self, user_id: str, discord_id: str) -> dict:
        """Get user's habit statistics"""
        if USE_LOCAL_ONLY:
            return self._get_local_stats(discord_id)
        
        try:
            result = supabase.table('checkins').select('*').eq('user_id', user_id).order('date', desc=True).execute()
            checkins = result.data
            
            if not checkins:
                return {'total': 0, 'current_streak': 0, 'best_streak': 0, 'recent': []}
            
            # Calculate stats
            total = len(checkins)
            current_streak = self._calculate_current_streak([c['date'] for c in checkins])
            best_streak = self._calculate_best_streak([c['date'] for c in checkins])
            recent = checkins[:5]  # Last 5 checkins
            
            return {
                'total': total,
                'current_streak': current_streak,
                'best_streak': best_streak,
                'recent': recent
            }
            
        except Exception as e:
            print(f"Database error: {e}")
            return self._get_local_stats(discord_id)
    
    def _get_local_stats(self, discord_id: str) -> dict:
        """Get stats from local JSON file"""
        try:
            if not os.path.exists(self.local_file):
                return {'total': 0, 'current_streak': 0, 'best_streak': 0, 'recent': []}
            
            with open(self.local_file, 'r') as f:
                data = json.load(f)
            
            if discord_id not in data:
                return {'total': 0, 'current_streak': 0, 'best_streak': 0, 'recent': []}
            
            checkins = sorted(data[discord_id], key=lambda x: x['date'], reverse=True)
            
            if not checkins:
                return {'total': 0, 'current_streak': 0, 'best_streak': 0, 'recent': []}
            
            total = len(checkins)
            dates = [c['date'] for c in checkins]
            current_streak = self._calculate_current_streak(dates)
            best_streak = self._calculate_best_streak(dates)
            recent = checkins[:5]
            
            return {
                'total': total,
                'current_streak': current_streak,
                'best_streak': best_streak,
                'recent': recent
            }
            
        except Exception as e:
            print(f"Local storage error: {e}")
            return {'total': 0, 'current_streak': 0, 'best_streak': 0, 'recent': []}
    
    def _calculate_current_streak(self, dates: list) -> int:
        """Calculate current streak from list of date strings"""
        if not dates:
            return 0
        
        # Sort dates in descending order
        sorted_dates = sorted([datetime.fromisoformat(d).date() if isinstance(d, str) else d for d in dates], reverse=True)
        
        today = date.today()
        streak = 0
        
        # Check if there's a checkin today or yesterday (to account for different timezones)
        if sorted_dates[0] == today:
            streak = 1
            check_date = today
        elif sorted_dates[0] == today.replace(day=today.day-1):
            streak = 1
            check_date = sorted_dates[0]
        else:
            return 0
        
        # Count consecutive days
        for i in range(1, len(sorted_dates)):
            expected_date = check_date.replace(day=check_date.day-1)
            if sorted_dates[i] == expected_date:
                streak += 1
                check_date = expected_date
            else:
                break
        
        return streak
    
    def _calculate_best_streak(self, dates: list) -> int:
        """Calculate best streak from list of date strings"""
        if not dates:
            return 0
        
        sorted_dates = sorted([datetime.fromisoformat(d).date() if isinstance(d, str) else d for d in dates])
        
        best_streak = 1
        current_streak = 1
        
        for i in range(1, len(sorted_dates)):
            if (sorted_dates[i] - sorted_dates[i-1]).days == 1:
                current_streak += 1
                best_streak = max(best_streak, current_streak)
            else:
                current_streak = 1
        
        return best_streak

# Initialize habit tracker
tracker = HabitTracker()

@bot.event
async def on_ready():
    print(f'{bot.user} has landed! Ready to help build habits.')
    print(f'Storage mode: {"Local JSON" if USE_LOCAL_ONLY else "Supabase"}')

@bot.command(name='checkin')
async def checkin(ctx, mood_or_message=None, *, message: str = None):
    """Log today's check-in with optional mood (1-5) and message
    
    Examples:
    !checkin                           # Simple check-in
    !checkin feeling great today!      # With message only
    !checkin 4                         # With mood only (4/5)
    !checkin 3 had an okay day         # With mood (3/5) and message
    """
    
    # Parse mood and message
    parsed_mood = None
    final_message = None
    
    if mood_or_message is not None:
        # Try to parse first argument as mood (1-5)
        try:
            potential_mood = int(mood_or_message)
            if 1 <= potential_mood <= 5:
                parsed_mood = potential_mood
                final_message = message  # Rest is the message
            else:
                # Not a valid mood, treat as part of message
                final_message = f"{mood_or_message} {message}" if message else mood_or_message
        except ValueError:
            # Not a number, treat as part of message
            final_message = f"{mood_or_message} {message}" if message else mood_or_message
    
    user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
    
    result = await tracker.add_checkin(
        user.get('id', str(ctx.author.id)), 
        str(ctx.author.id), 
        final_message,
        parsed_mood
    )
    
    if result['success']:
        # New checkin - success!
        response = "✅ Checked in for today!"
        
        if parsed_mood:
            mood_emojis = ["", "😔", "😕", "😐", "😊", "😄"]
            mood_labels = ["", "struggling", "tough day", "okay", "good", "great"]
            response += f"\n🎭 **Mood:** {parsed_mood}/5 {mood_emojis[parsed_mood]} ({mood_labels[parsed_mood]})"
        
        if final_message:
            response += f"\n💭 *\"{final_message}\"*"
        
        response += "\n\nNice work showing up! 🌱"
        await ctx.send(response)
        
    elif result['existing']:
        # Existing checkin - ask for confirmation
        existing = result['existing']
        mood_emojis = ["", "😔", "😕", "😐", "😊", "😄"]
        
        # Format existing checkin
        existing_text = ""
        if existing.get('mood'):
            existing_text += f"{existing['mood']}/5 {mood_emojis[existing['mood']]} "
        if existing.get('message'):
            existing_text += f'"{existing["message"]}"'
        if not existing_text:
            existing_text = "simple check-in"
        
        # Format new checkin
        new_text = ""
        if parsed_mood:
            new_text += f"{parsed_mood}/5 {mood_emojis[parsed_mood]} "
        if final_message:
            new_text += f'"{final_message}"'
        if not new_text:
            new_text = "simple check-in"
        
        confirmation_msg = await ctx.send(
            f"🤔 **You already checked in today!**\n\n"
            f"**Current:** {existing_text}\n"
            f"**New:** {new_text}\n\n"
            f"Do you want to override your existing check-in?\n"
            f"✅ = Yes, update it\n"
            f"❌ = No, keep the original"
        )
        
        # Add reaction options
        await confirmation_msg.add_reaction("✅")
        await confirmation_msg.add_reaction("❌")
        
        # Wait for user reaction
        def check_reaction(reaction, user):
            return (user == ctx.author and 
                   str(reaction.emoji) in ["✅", "❌"] and 
                   reaction.message.id == confirmation_msg.id)
        
        try:
            reaction, user = await bot.wait_for('reaction_add', timeout=30.0, check=check_reaction)
            
            if str(reaction.emoji) == "✅":
                # User confirmed - update the checkin
                update_success = await tracker.update_checkin(
                    user.get('id', str(ctx.author.id)),
                    str(ctx.author.id),
                    final_message,
                    parsed_mood
                )
                
                if update_success:
                    response = "✅ **Updated your check-in for today!**"
                    
                    if parsed_mood:
                        mood_labels = ["", "struggling", "tough day", "okay", "good", "great"]
                        response += f"\n🎭 **New mood:** {parsed_mood}/5 {mood_emojis[parsed_mood]} ({mood_labels[parsed_mood]})"
                    
                    if final_message:
                        response += f"\n💭 *\"{final_message}\"*"
                    
                    response += "\n\nNice work staying mindful! 🌱"
                    await ctx.send(response)
                else:
                    await ctx.send("❌ Something went wrong updating your check-in. Try again?")
            else:
                # User cancelled
                await ctx.send("👍 Keeping your original check-in. No changes made!")
                
        except asyncio.TimeoutError:
            await ctx.send("⏰ Confirmation timed out. Keeping your original check-in!")
            
    else:
        await ctx.send("❌ Something went wrong with your check-in. Try again?")

@bot.command(name='summary')
async def summary(ctx):
    """View your habit summary"""
    user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
    stats = await tracker.get_user_stats(user.get('id', str(ctx.author.id)), str(ctx.author.id))
    
    embed = discord.Embed(title="📊 Your Habit Summary", color=0x22c55e)
    embed.add_field(name="Total Check-ins", value=stats['total'], inline=True)
    embed.add_field(name="Current Streak", value=f"{stats['current_streak']} days", inline=True)
    embed.add_field(name="Best Streak", value=f"{stats['best_streak']} days", inline=True)
    
    if stats['recent']:
        recent_text = ""
        for checkin in stats['recent'][:3]:
            date_str = checkin.get('date', 'Unknown')
            message = checkin.get('message', 'No message')
            mood = checkin.get('mood')
            
            line = f"**{date_str}**: {message}"
            if mood:
                mood_emojis = ["", "😔", "😕", "😐", "😊", "😄"]
                line += f" ({mood}/5 {mood_emojis[mood]})"
            recent_text += line + "\n"
        embed.add_field(name="Recent Check-ins", value=recent_text, inline=False)
    
    await ctx.send(embed=embed)

@bot.command(name='reflect')
async def reflect(ctx):
    """Get AI reflection on your habits"""
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        await ctx.send("🤖 AI features aren't configured yet. The bot admin needs to add an OpenAI API key!")
        return
    
    user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
    stats = await tracker.get_user_stats(user.get('id', str(ctx.author.id)), str(ctx.author.id))
    
    if stats['total'] == 0:
        await ctx.send("🤖 You haven't checked in yet! Try `!checkin` first, then I can give you some perspective.")
        return
    
    try:
        client = openai.OpenAI(api_key=openai_key)
        
        # Prepare context about user's habits
        context = f"""
        User stats:
        - Total check-ins: {stats['total']}
        - Current streak: {stats['current_streak']} days
        - Best streak: {stats['best_streak']} days
        
        Recent check-ins:
        """
        
        for checkin in stats['recent'][:5]:
            date_str = checkin.get('date', 'Unknown')
            message = checkin.get('message', 'No message')
            context += f"- {date_str}: {message}\n"
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DR_K_SYSTEM_PROMPT},
                {"role": "user", "content": f"Give me some perspective on my habit tracking progress: {context}"}
            ],
            max_tokens=200
        )
        
        reflection = response.choices[0].message.content
        await ctx.send(f"🤖 **Reflection:**\n{reflection}")
        
    except Exception as e:
        print(f"OpenAI error: {e}")
        await ctx.send("🤖 Couldn't generate reflection right now. The AI is probably having a moment.")

@bot.command(name='rewrite')
async def rewrite(ctx, *, text: str):
    """Rewrite negative thoughts positively"""
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        await ctx.send("🤖 AI features aren't configured yet. The bot admin needs to add an OpenAI API key!")
        return
    
    try:
        client = openai.OpenAI(api_key=openai_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DR_K_SYSTEM_PROMPT + "\n\nReframe the user's negative self-talk in a more compassionate, realistic way. Don't dismiss their feelings, but help them see a more balanced perspective."},
                {"role": "user", "content": f"Help me reframe this thought: {text}"}
            ],
            max_tokens=150
        )
        
        reframed = response.choices[0].message.content
        await ctx.send(f"🤖 **Reframed:**\n{reframed}")
        
    except Exception as e:
        print(f"OpenAI error: {e}")
        await ctx.send("🤖 Couldn't rewrite that right now. Sometimes the AI needs a break too.")

@bot.command(name='idea')
async def idea(ctx):
    """Get a small habit-building idea"""
    openai_key = os.getenv('OPENAI_API_KEY')
    
    if not openai_key:
        await ctx.send("🤖 AI features aren't configured yet. The bot admin needs to add an OpenAI API key!")
        return
    
    try:
        client = openai.OpenAI(api_key=openai_key)
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": DR_K_SYSTEM_PROMPT + "\n\nSuggest a small, actionable habit-building idea. Keep it simple and achievable. Focus on tiny steps that build momentum."},
                {"role": "user", "content": "Give me a small idea for building better habits or self-care."}
            ],
            max_tokens=150
        )
        
        suggestion = response.choices[0].message.content
        await ctx.send(f"💡 **Small idea:**\n{suggestion}")
        
    except Exception as e:
        print(f"OpenAI error: {e}")
        await ctx.send("💡 The idea generator is taking a nap. Try again in a bit!")

@bot.command(name='commands')
async def commands_list(ctx):
    """Show available commands"""
    embed = discord.Embed(
        title="🌱 HabitualAI Commands", 
        description="Your gentle companion for building consistency",
        color=0x22c55e
    )
    
    embed.add_field(
        name="📝 Basic Commands",
        value="`!checkin [mood] [message]` - Log today's check-in\n`!summary` - View your stats and recent entries\n`!timezone [zone]` - Set your timezone (resets at local midnight)\n`!remindme 20:00 CET` - Set daily reminder with timezone\n`!stopreminder` - Turn off reminders",
        inline=False
    )
    
    embed.add_field(
        name="🎭 Mood Tracking Examples",
        value="`!checkin` - Simple check-in\n`!checkin 4` - Mood only (4/5 😊)\n`!checkin 3 had an okay day` - Mood + message\n`!checkin feeling great!` - Message only",
        inline=False
    )
    
    embed.add_field(
        name="🤖 AI Features",
        value="`!reflect` - Get perspective on your progress\n`!rewrite [text]` - Reframe negative thoughts\n`!idea` - Get a small habit-building suggestion",
        inline=False
    )
    
    embed.add_field(
        name="💡 Tips",
        value="• Check in daily, even with just `!checkin`\n• Be honest about struggles - this tool won't judge\n• Small steps count more than perfect streaks\n• Use `!commands` to see this help again",
        inline=False
    )
    
    await ctx.send(embed=embed)

@bot.command(name='timezone')
async def set_timezone(ctx, *, timezone_str: str = None):
    """Set your timezone for proper check-in timing (e.g., !timezone CET or !timezone Europe/Stockholm)"""
    if not timezone_str:
        # Show current timezone
        user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
        
        if not USE_LOCAL_ONLY and supabase:
            try:
                result = supabase.table('users').select('timezone').eq('discord_id', str(ctx.author.id)).execute()
                if result.data and result.data[0].get('timezone'):
                    current_tz = result.data[0]['timezone']
                    user_tz = pytz.timezone(current_tz)
                    now_local = datetime.now(user_tz)
                    await ctx.send(f"🌍 Your timezone: **{current_tz}**\nLocal time: **{now_local.strftime('%Y-%m-%d %H:%M')}**\n\nCheck-ins reset at midnight in your local time! 🕛")
                else:
                    await ctx.send("🌍 No timezone set. Using UTC (server time).\n\nSet your timezone with: `!timezone Europe/Stockholm` or `!timezone CET`")
            except Exception as e:
                await ctx.send("🌍 No timezone set. Using UTC (server time).\n\nSet your timezone with: `!timezone Europe/Stockholm` or `!timezone CET`")
        else:
            await ctx.send("🌍 Local mode - using server timezone.\n\nSet your timezone with: `!timezone Europe/Stockholm` or `!timezone CET`")
        return
    
    # Timezone mapping for common abbreviations
    timezone_mapping = {
        'CET': 'Europe/Berlin',
        'CEST': 'Europe/Berlin', 
        'EST': 'US/Eastern',
        'EDT': 'US/Eastern',
        'PST': 'US/Pacific',
        'PDT': 'US/Pacific',
        'GMT': 'GMT',
        'UTC': 'UTC',
        'CST': 'US/Central',
        'CDT': 'US/Central',
        'MST': 'US/Mountain',
        'MDT': 'US/Mountain',
        'JST': 'Asia/Tokyo',
        'BST': 'Europe/London',
        'STOCKHOLM': 'Europe/Stockholm',
        'SWEDEN': 'Europe/Stockholm'
    }
    
    # Get timezone
    if timezone_str.upper() in timezone_mapping:
        tz_name = timezone_mapping[timezone_str.upper()]
        try:
            user_tz = pytz.timezone(tz_name)
        except pytz.UnknownTimeZoneError:
            await ctx.send(f"❌ Error with timezone: `{tz_name}`")
            return
    else:
        # Try to use it as a timezone name directly
        try:
            user_tz = pytz.timezone(timezone_str)
            tz_name = timezone_str
        except pytz.UnknownTimeZoneError:
            await ctx.send(f"❌ Unknown timezone: `{timezone_str}`\n\n**Supported shortcuts:** CET, EST, PST, GMT, UTC, CST, MST, JST, BST, STOCKHOLM\n**Or use full names:** Europe/Stockholm, US/Eastern, Asia/Tokyo")
            return
    
    # Store timezone for user
    user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
    
    if not USE_LOCAL_ONLY and supabase:
        try:
            supabase.table('users').update({
                'timezone': tz_name
            }).eq('discord_id', str(ctx.author.id)).execute()
        except Exception as e:
            print(f"Database error updating timezone: {e}")
    
    # Show confirmation with local time
    now_local = datetime.now(user_tz)
    await ctx.send(f"🌍 Timezone set to **{tz_name}**!\nYour local time: **{now_local.strftime('%Y-%m-%d %H:%M')}**\n\n✨ Check-ins now reset at midnight in your local time!")

@bot.command(name='remindme')
async def set_reminder(ctx, reminder_time: str = None, timezone_str: str = "UTC"):
    """Set a daily reminder time with timezone (e.g., !remindme 20:00 CET or !remindme 9 EST)"""
    if not reminder_time:
        await ctx.send("🕐 Please specify a time! Examples:\n`!remindme 20:00 CET` - 8 PM Central European Time\n`!remindme 9 EST` - 9 AM Eastern Time\n`!remindme 14:30` - 2:30 PM UTC (default)")
        return
    
    try:
        # Handle different time formats
        if ':' in reminder_time:
            # HH:MM format
            hour, minute = map(int, reminder_time.split(':'))
        else:
            # Just hour format (e.g., "9" or "21")
            hour = int(reminder_time)
            minute = 0
        
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("Invalid time range")
        
        # Parse timezone
        timezone_mapping = {
            'CET': 'Europe/Berlin',
            'CEST': 'Europe/Berlin', 
            'EST': 'US/Eastern',
            'EDT': 'US/Eastern',
            'PST': 'US/Pacific',
            'PDT': 'US/Pacific',
            'GMT': 'GMT',
            'UTC': 'UTC',
            'CST': 'US/Central',
            'CDT': 'US/Central',
            'MST': 'US/Mountain',
            'MDT': 'US/Mountain',
            'JST': 'Asia/Tokyo',
            'BST': 'Europe/London'
        }
        
        # Get timezone
        if timezone_str.upper() in timezone_mapping:
            tz_name = timezone_mapping[timezone_str.upper()]
            user_tz = pytz.timezone(tz_name)
        else:
            # Try to use it as a timezone name directly
            try:
                user_tz = pytz.timezone(timezone_str)
            except pytz.UnknownTimeZoneError:
                await ctx.send(f"❌ Unknown timezone: `{timezone_str}`\n\nSupported: CET, EST, PST, GMT, UTC, CST, MST, JST, BST\nOr use full names like `Europe/Berlin`, `US/Eastern`")
                return
        
        # Convert to UTC for storage
        local_time = user_tz.localize(datetime.combine(date.today(), time(hour, minute)))
        utc_time = local_time.astimezone(pytz.UTC).time()
        
        # Store reminder time and timezone for user
        user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
        
        if not USE_LOCAL_ONLY and supabase:
            try:
                # Update user's reminder time and timezone in database
                supabase.table('users').update({
                    'reminder_time': utc_time.isoformat(),
                    'timezone': str(user_tz)
                }).eq('discord_id', str(ctx.author.id)).execute()
            except Exception as e:
                print(f"Database error updating reminder: {e}")
        
        # Format display time
        display_time = f"{hour:02d}:{minute:02d}"
        await ctx.send(f"⏰ Daily reminder set for **{display_time} {timezone_str.upper()}**!\n\nI'll send you a DM if you haven't checked in by then. 🌱\n\n*Stored as {utc_time.strftime('%H:%M')} UTC internally*")
        
        # Start the reminder task if not already running
        if not daily_reminder_check.is_running():
            daily_reminder_check.start()
            
    except ValueError as e:
        await ctx.send("❌ Invalid time format! Examples:\n`!remindme 20:00 CET` - 8 PM Central European Time\n`!remindme 9 EST` - 9 AM Eastern Time\n`!remindme 14:30` - 2:30 PM UTC")

@bot.command(name='stopreminder')
async def stop_reminder(ctx):
    """Stop daily reminders"""
    user = await tracker.get_or_create_user(str(ctx.author.id), str(ctx.author))
    
    if not USE_LOCAL_ONLY and supabase:
        try:
            # Remove reminder time from database
            supabase.table('users').update({
                'reminder_time': None
            }).eq('discord_id', str(ctx.author.id)).execute()
        except Exception as e:
            print(f"Database error removing reminder: {e}")
    
    await ctx.send("🔕 Daily reminders stopped. You can set them again with `!remindme HH:MM`")

@tasks.loop(minutes=30)  # Check every 30 minutes
async def daily_reminder_check():
    """Check if users need reminders"""
    if USE_LOCAL_ONLY:
        return  # Skip reminders in local mode for now
    
    try:
        current_time = datetime.utcnow().time()
        current_date = date.today()
        
        # Get users who have reminder times set
        result = supabase.table('users').select('*').not_.is_('reminder_time', 'null').execute()
        
        for user_data in result.data:
            user_id = user_data['id']
            discord_id = user_data['discord_id']
            reminder_time_str = user_data['reminder_time']
            
            if not reminder_time_str:
                continue
                
            # Parse reminder time
            reminder_time = datetime.fromisoformat(f"1900-01-01T{reminder_time_str}").time()
            
            # Check if it's time to remind (within 30 minutes of reminder time)
            time_diff = datetime.combine(current_date, current_time) - datetime.combine(current_date, reminder_time)
            
            if abs(time_diff.total_seconds()) <= 1800:  # Within 30 minutes
                # Check if user has already checked in today
                checkin_result = supabase.table('checkins').select('*').eq('user_id', user_id).eq('date', current_date.isoformat()).execute()
                
                if not checkin_result.data:  # No checkin today
                    # Send reminder DM
                    try:
                        discord_user = await bot.fetch_user(int(discord_id))
                        
                        embed = discord.Embed(
                            title="🌱 Gentle Reminder",
                            description="Hey there! Just checking in - you haven't logged your daily check-in yet.",
                            color=0x22c55e
                        )
                        embed.add_field(
                            name="Quick Check-in",
                            value="Just type `!checkin` in any server where I'm present, or add a message like `!checkin had a good day!`",
                            inline=False
                        )
                        embed.add_field(
                            name="Remember",
                            value="Consistency isn't about perfection. Even checking in with 'struggled today' counts as showing up. 💚",
                            inline=False
                        )
                        embed.set_footer(text="Use !stopreminder if you want to turn these off")
                        
                        await discord_user.send(embed=embed)
                        print(f"Sent reminder to {discord_user.name}")
                        
                    except discord.Forbidden:
                        print(f"Couldn't send DM to user {discord_id} - DMs disabled")
                    except discord.NotFound:
                        print(f"User {discord_id} not found")
                    except Exception as e:
                        print(f"Error sending reminder to {discord_id}: {e}")
                        
    except Exception as e:
        print(f"Error in reminder check: {e}")

@daily_reminder_check.before_loop
async def before_reminder_check():
    await bot.wait_until_ready()

if __name__ == "__main__":
    if not DISCORD_TOKEN:
        print("❌ DISCORD_TOKEN not found in environment variables!")
        exit(1)
    
    bot.run(DISCORD_TOKEN) 