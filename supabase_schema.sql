-- Users table
create table if not exists users (
  id uuid primary key default gen_random_uuid(),
  discord_id text unique not null,
  discord_username text,
  reminder_time time,
  timezone text default 'UTC',
  created_at timestamp default now(),
  updated_at timestamp default now()
);

-- Checkins table
create table if not exists checkins (
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
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'users' and policyname = 'Users can view own data') then
    create policy "Users can view own data" on users
      for select using (auth.uid()::text = discord_id);
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'users' and policyname = 'Users can update own data') then
    create policy "Users can update own data" on users
      for update using (auth.uid()::text = discord_id);
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'users' and policyname = 'Users can insert own data') then
    create policy "Users can insert own data" on users
      for insert with check (auth.uid()::text = discord_id);
  end if;
end $$;

-- Checkins policies
do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'checkins' and policyname = 'Users can view own checkins') then
    create policy "Users can view own checkins" on checkins
      for select using (
        user_id in (select id from users where discord_id = auth.uid()::text)
      );
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'checkins' and policyname = 'Users can insert own checkins') then
    create policy "Users can insert own checkins" on checkins
      for insert with check (
        user_id in (select id from users where discord_id = auth.uid()::text)
      );
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'checkins' and policyname = 'Users can update own checkins') then
    create policy "Users can update own checkins" on checkins
      for update using (
        user_id in (select id from users where discord_id = auth.uid()::text)
      );
  end if;
end $$;

do $$ begin
  if not exists (select 1 from pg_policies where tablename = 'checkins' and policyname = 'Users can delete own checkins') then
    create policy "Users can delete own checkins" on checkins
      for delete using (
        user_id in (select id from users where discord_id = auth.uid()::text)
      );
  end if;
end $$;

-- Indexes for performance
create index if not exists idx_users_discord_id on users(discord_id);
create index if not exists idx_checkins_user_id on checkins(user_id);
create index if not exists idx_checkins_date on checkins(date);
create index if not exists idx_checkins_user_date on checkins(user_id, date);

-- Function to update updated_at timestamp
create or replace function update_updated_at_column()
returns trigger as $$
begin
  new.updated_at = now();
  return new;
end;
$$ language plpgsql;

-- Trigger to automatically update updated_at
do $$ begin
  if not exists (select 1 from pg_trigger where tgname = 'update_users_updated_at') then
    create trigger update_users_updated_at
      before update on users
      for each row
      execute function update_updated_at_column();
  end if;
end $$;

-- Function to create user (bypasses RLS for bot usage)
create or replace function create_user_if_not_exists(
  p_discord_id text,
  p_discord_username text default null
)
returns users
language plpgsql
security definer -- This allows the function to bypass RLS
as $$
declare
  result_user users;
begin
  -- Try to get existing user first
  select * into result_user
  from users
  where discord_id = p_discord_id;
  
  -- If user doesn't exist, create them
  if result_user is null then
    insert into users (discord_id, discord_username)
    values (p_discord_id, p_discord_username)
    returning * into result_user;
  end if;
  
  return result_user;
end;
$$;

-- Function to create or update checkin (bypasses RLS for bot usage)
create or replace function create_or_update_checkin(
  p_user_discord_id text,
  p_date date,
  p_message text default null,
  p_mood integer default null
)
returns checkins
language plpgsql
security definer
as $$
declare
  user_record users;
  result_checkin checkins;
begin
  -- Get or create user first
  select * into user_record from create_user_if_not_exists(p_user_discord_id);
  
  -- Insert or update checkin
  insert into checkins (user_id, date, message, mood)
  values (user_record.id, p_date, p_message, p_mood)
  on conflict (user_id, date)
  do update set 
    message = excluded.message,
    mood = excluded.mood,
    created_at = now()
  returning * into result_checkin;
  
  return result_checkin;
end;
$$;

-- Grant execute permissions to service role
grant execute on function create_user_if_not_exists(text, text) to service_role;
grant execute on function create_or_update_checkin(text, date, text, integer) to service_role; 