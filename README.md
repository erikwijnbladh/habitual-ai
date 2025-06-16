# ⏳ HabitualAI

> Show up. Log the day. Build identity through action.  
> A Discord bot + web app that helps you stay consistent and reflect — with your own data and AI keys.

---

## 🌱 Why?

If you've ever said:

- "I want to build myself back up"
- "I can't stay consistent"
- "I know what I want but I can't seem to do it"

This is for you.

A **minimal, frictionless habit tracker** with Discord logging and web analytics.  
Log check-ins in Discord. View insights on the web. Use your own AI keys.  
**Self-hostable, privacy-first, and free forever.**

---

## 🚀 Quick Start

### 🏠 **Local Development (Recommended for testing)**

Perfect for trying out the bot without any database setup:

```bash
# 1. Clone and install
git clone <your-repo>
cd habitual-ai
pip install -r requirements.txt

# 2. Quick local setup
cp env.example .env
# Edit .env and set:
# DISCORD_TOKEN=your_bot_token
# USE_LOCAL_ONLY=true
# OPENAI_API_KEY=your_key (optional)

# 3. Run the bot
cd bot && python bot.py
```

**✅ Local Benefits:** No database setup, data in `checkins.json`, perfect for testing

### 🌐 **Production Deployment**

For multi-user deployment with web dashboard:

```bash
# 1. Setup Supabase database (see Supabase Setup section)
# 2. Use production environment
cp env.production.example .env
# Fill in all production values

# 3. Deploy to Fly.io, Railway, Heroku, etc.
```

**✅ Production Benefits:** Multi-user, web dashboard, persistent storage

---

## ✅ Features

### 🤖 Discord Bot

| Command               | Description                                                    |
| --------------------- | -------------------------------------------------------------- |
| `!checkin [msg]`      | Log today's check-in (stored locally or in Supabase)           |
| `!summary`            | View streak, total logs, and recent entries                    |
| `!remindme 20:00 CET` | Set a daily DM reminder with timezone support                  |
| `!stopreminder`       | Turn off daily reminders                                       |
| `!commands`           | Show all available commands                                    |
| `!reflect`            | _(with your OpenAI key)_ Get GPT summary and encouragement     |
| `!rewrite [text]`     | _(with your OpenAI key)_ GPT rephrases your journal positively |
| `!idea`               | _(with your OpenAI key)_ GPT suggests small growth ideas       |

### 🌐 Web Dashboard

- **Real-time Analytics**: Calendar heatmaps, streak trends, mood patterns
- **Live Updates**: Changes from Discord appear instantly in web app
- **Data Management**: Import local JSON, export to CSV/JSON
- **AI Integration**: Use your own OpenAI API key for insights
- **Settings**: Configure reminders, prompts, and preferences
- **Modern UI**: Built with ShadCN/UI in black/white/green theme

---

## 🧠 Modes

### 🔌 Supabase Mode (default)

- Stores data in **Supabase** (PostgreSQL)
- Real-time sync between Discord bot and web dashboard
- Built-in authentication with Discord OAuth
- Row-level security ensures data privacy

### 🔒 Local-Only Mode

- No database required
- Stores all logs in `checkins.json`
- Import to web app for analytics
- Perfect for offline or privacy-focused users

Enable local mode via:

```env
USE_LOCAL_ONLY=true
```

---

## 🧱 Tech Stack

### Backend

- **Python 3.10+** with Discord.py
- `supabase-py` for database operations
- `apscheduler` for reminders
- `openai` _(with your API key)_ for reflection

### Frontend

- **Vite + React 18** with TypeScript
- **ShadCN/UI** components (black/white/green theme)
- **Tailwind CSS** for styling
- **Recharts** for analytics visualization
- **Supabase JS** for real-time data
- **Lucide React** for icons

### Database

- **Supabase** (managed PostgreSQL)
- Real-time subscriptions
- Built-in authentication
- Row Level Security

---

## 📁 File Structure

<details>
<summary>🗂️ Click to expand project structure</summary>

```
habitual-ai/
├── bot/
│   ├── bot.py                # Discord bot entry point
│   ├── storage.py            # Supabase/local storage abstraction
│   ├── local_storage.py      # JSON storage fallback
│   ├── supabase_client.py    # Supabase connection
│   └── commands/             # Bot command handlers
├── web/
│   ├── src/
│   │   ├── components/       # ShadCN/UI components
│   │   │   ├── ui/           # Base ShadCN components
│   │   │   ├── dashboard/    # Dashboard-specific components
│   │   │   └── analytics/    # Chart and analytics components
│   │   ├── lib/
│   │   │   ├── supabase.ts   # Supabase client configuration
│   │   │   └── utils.ts      # Utility functions
│   │   ├── hooks/            # Custom React hooks
│   │   ├── pages/            # React Router pages
│   │   └── styles/           # Global styles and themes
│   ├── package.json
│   └── vite.config.ts
├── supabase/
│   ├── migrations/           # Database schema migrations
│   ├── seed.sql             # Sample data for development
│   └── config.toml          # Supabase configuration
├── shared/
│   ├── types.py             # Shared Python types
│   └── config.py            # Environment configuration
├── requirements.txt
├── docker-compose.yml
└── README.md
```

</details>

---

## ⚙️ Environment Setup

Create a `.env` file:

```env
# Discord Bot
DISCORD_TOKEN=your_discord_bot_token

# Supabase (optional - uses local JSON if not provided)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE=your_supabase_service_role_key_here
# or
USE_LOCAL_ONLY=true

# AI Features (optional - users can add their own keys in web UI)
OPENAI_API_KEY=your_openai_key
```

For the React app, create `web/.env`:

```env
VITE_SUPABASE_URL=https://your-project.supabase.co
VITE_SUPABASE_ANON_KEY=your_supabase_anon_key  # Use ANON key for web app (not service role)
VITE_USE_LOCAL_ONLY=false
```

---

## 🗄️ Supabase Setup

### 1. Create a Supabase Project

Go to [supabase.com](https://supabase.com) and create a free project.

### 2. Run Database Migration

<details>
<summary>📋 Click to expand SQL schema</summary>

In the Supabase SQL Editor, run:

```sql
-- Users table
create table users (
  id uuid primary key default gen_random_uuid(),
  discord_id text unique not null,
  discord_username text,
  openai_api_key text, -- encrypted, user-provided
  reminder_time time,
  timezone text default 'UTC',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

-- Checkins table
create table checkins (
  id uuid primary key default gen_random_uuid(),
  user_id uuid references users(id) on delete cascade,
  date date not null,
  message text,
  mood integer check (mood >= 1 and mood <= 5),
  created_at timestamp default now(),
  unique(user_id, date)
);

-- Row Level Security
alter table users enable row level security;
alter table checkins enable row level security;

-- Users can only see their own data
create policy "Users can view own data" on users
  for select using (auth.uid()::text = discord_id);

create policy "Users can update own data" on users
  for update using (auth.uid()::text = discord_id);

create policy "Users can insert own data" on users
  for insert with check (auth.uid()::text = discord_id);

-- Checkins policies
create policy "Users can view own checkins" on checkins
  for select using (
    user_id in (select id from users where discord_id = auth.uid()::text)
  );

create policy "Users can insert own checkins" on checkins
  for insert with check (
    user_id in (select id from users where discord_id = auth.uid()::text)
  );

create policy "Users can update own checkins" on checkins
  for update using (
    user_id in (select id from users where discord_id = auth.uid()::text)
  );

create policy "Users can delete own checkins" on checkins
  for delete using (
    user_id in (select id from users where discord_id = auth.uid()::text)
  );

-- Indexes for performance
create index idx_users_discord_id on users(discord_id);
create index idx_checkins_user_id on checkins(user_id);
create index idx_checkins_date on checkins(date);
create index idx_checkins_user_date on checkins(user_id, date);

-- Function to update updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Trigger to automatically update updated_at
create trigger update_users_updated_at
  before update on users
  for each row
  execute function update_updated_at_column();
```

</details>

### 3. Get Your Service Role Key

**⚠️ Important:** The Discord bot needs the **service role key** (not the anon key) to bypass Row Level Security.

1. Go to **Settings** → **API** in your Supabase dashboard
2. Copy the **"service_role"** key (the long one, not the anon key)
3. Use this as your `SUPABASE_SERVICE_ROLE` in the bot's `.env` file

### 4. Enable Discord OAuth (Optional - for web app)

1. Go to Authentication → Providers
2. Enable Discord provider
3. Add your Discord app credentials

---

## 🎨 Design System

The web app uses **ShadCN/UI** with the official **Green theme**:

- **Primary**: Green accents for actions and highlights
- **Background**: Clean black/white with proper contrast
- **Typography**: Modern, readable font stack
- **Accessibility**: ARIA labels, keyboard navigation, high contrast
- **Responsive**: Mobile-friendly but desktop-optimized

### ShadCN Green Theme

Uses the built-in green theme from ShadCN/UI with OKLCH color space for better color consistency:

```css
/* Light mode */
--primary: oklch(0.723 0.219 149.579);
--primary-foreground: oklch(0.982 0.018 155.826);

/* Dark mode */
--primary: oklch(0.696 0.17 162.48);
--primary-foreground: oklch(0.393 0.095 152.535);
```

### Real-time Features

```typescript
// Real-time checkin updates
const { data: checkins } = useSupabaseQuery("checkins");

useEffect(() => {
  const subscription = supabase
    .channel("checkins")
    .on(
      "postgres_changes",
      { event: "*", schema: "public", table: "checkins" },
      (payload) => {
        // Update UI instantly when Discord bot adds checkin
        updateCheckins(payload.new);
      }
    )
    .subscribe();

  return () => subscription.unsubscribe();
}, []);
```

---

## 🚀 Local Development

### 1. Start Supabase locally

```bash
npx supabase start
```

### 2. Run Discord Bot

```bash
cd bot/
pip install -r requirements.txt
python bot.py
```

### 3. Run Web App

```bash
cd web/
npm install
npm run dev
```

### 4. Access the app

- Web Dashboard: http://localhost:5173
- Supabase Studio: http://localhost:54323

---

## 📦 Dependencies

<details>
<summary>📋 Click to expand dependency lists</summary>

### Bot Requirements (`requirements.txt`)

```txt
discord.py==2.3.2
supabase==2.0.0
openai==1.3.0
python-dotenv==1.0.0
pytz==2023.3
asyncio
```

### Web App (`web/package.json`)

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "@supabase/supabase-js": "^2.38.0",
    "recharts": "^2.8.0",
    "lucide-react": "^0.294.0",
    "@radix-ui/react-*": "latest"
  }
}
```

</details>

---

## 🧪 Example Usage

### Real-time Dashboard Updates

1. Type `!checkin feeling great today!` in Discord
2. Web dashboard instantly shows new checkin
3. Streak counter updates in real-time
4. Analytics charts refresh automatically

### Dr. K-Style AI Responses

**`!reflect` after a good week:**

> "Look, you've checked in 5 out of 7 days this week, and that's actually really solid. Here's the thing - you're building something real here. I notice you missed the weekend, which is super common. Weekends mess with our routines, and that's just human. The fact that you got back to it Monday? That's the real win."

**`!rewrite "I'm such a failure, missed 3 days in a row"`:**

> "You're going through a rough patch, and that's part of being human. Missing three days doesn't erase the progress you've made - it just means life happened. The story isn't over because you had a hard week."

**`!idea` when struggling:**

> "Here's something small you could try: instead of committing to checking in every day, what if you just committed to opening Discord? That's it. Sometimes we need to make the bar so low that we can't fail. Build the habit of showing up first, then worry about the perfect check-in later."

### Smart Reminder System

**Set timezone-aware reminders:**

```
!remindme 9 CET          # 9 AM Central European Time
!remindme 20:30 EST      # 8:30 PM Eastern Time
!remindme 14 PST         # 2 PM Pacific Time
!stopreminder            # Turn off reminders
```

**Supported timezones:** CET, EST, PST, GMT, UTC, CST, MST, JST, BST, or full names like `Europe/Berlin`, `US/Eastern`

**Gentle reminder DMs:**

> **🌱 Gentle Reminder**
>
> Hey there! Just checking in - you haven't logged your daily check-in yet.
>
> **Remember:** Consistency isn't about perfection. Even checking in with 'struggled today' counts as showing up. 💚

### AI Integration

<details>
<summary>🤖 Click to expand AI implementation details</summary>

```typescript
// User adds their OpenAI key in web settings
const handleReflection = async () => {
  const response = await openai.chat.completions.create({
    model: "gpt-4o-mini",
    messages: [
      {
        role: "system",
        content: `You are a compassionate but realistic habit coach inspired by Dr. K from HealthyGamerGG. 
        
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
        - Corporate wellness speak`,
      },
      {
        role: "user",
        content: `Analyze my recent habit data and give me some perspective: ${recentCheckins}`,
      },
    ],
  });
  // Display AI insights in dashboard
};
```

</details>

---

## 🔧 Troubleshooting

### Bot can't create users/checkins (RLS errors)

**Problem:** Getting "new row violates row-level security policy" errors.

**Solution:** Make sure you're using the **service role key** (not anon key) in your bot's `.env` file:

```env
SUPABASE_SERVICE_ROLE=your_supabase_service_role_key_here
```

The service role key bypasses Row Level Security, which is necessary for the bot to create users and checkins on behalf of Discord users.

### Discord bot not responding to commands

1. **Check Message Content Intent:** Go to Discord Developer Portal → Your App → Bot → Privileged Gateway Intents → Enable "Message Content Intent"
2. **Check bot permissions:** Ensure bot has "Send Messages" and "Read Message History" permissions in your server
3. **Check console output:** Look for connection errors or permission issues in the terminal

### Python/Discord.py issues

- **Use Python 3.12:** Discord.py has compatibility issues with Python 3.13
- **Install requirements:** Make sure all dependencies are installed: `pip install -r requirements.txt`

### Timezone reminders not working

- **Valid timezone:** Use standard timezone names like `CET`, `EST`, `PST`, `UTC`
- **Time format:** Use 24-hour format: `!remindme 9 CET` (for 9:00 AM)
- **Check logs:** Bot logs reminder scheduling in the console

### Database connection issues

- **Local mode:** Set `USE_LOCAL_ONLY=true` in `.env` to use JSON file storage instead
- **Supabase URL:** Make sure your Supabase URL is correct and project is not paused
- **API keys:** Double-check you're using the right keys (service role for bot, anon for web app)

### Environment setup confusion

- **Local development:** Use `env.example` → set `USE_LOCAL_ONLY=true`
- **Production deployment:** Use `env.production.example` → set `USE_LOCAL_ONLY=false`
- **Mixed setup:** Don't mix local and production settings in same environment

---

## 🧠 Philosophy

This is not a productivity app.

It's a quiet space in your Discord where you can:

- Reconnect with intention
- Track what matters to you
- Build slowly, without judgment

It's a tool for effort, not ego.

---

## 💬 Contributions Welcome

Want to add:

- Mood tracking visualizations
- Voice logging integration
- Team habit challenges
- Custom analytics widgets

Fork it. Remix it. Or open a PR.  
This is for anyone who wants to build something real.

---

## 📄 License

MIT — free to use, modify, and distribute.

Please don't turn this into a startup that shames people into journaling.

---

## 🌍 Credit

- Inspired by [Dr. K (HealthyGamerGG)](https://youtube.com/@HealthyGamerGG)
- GPT via [OpenAI](https://openai.com)
- Dev stack by [Supabase](https://supabase.com), [Discord.py](https://discordpy.readthedocs.io/)
- UI components by [ShadCN/UI](https://ui.shadcn.com/)

---

## 🧭 Stay Human

This is not a bot for being more productive.  
It's a companion for showing up on the days when that's all you can do.

> "Build yourself, gently."
