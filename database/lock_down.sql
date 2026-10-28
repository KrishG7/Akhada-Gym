-- Run this in the Supabase SQL editor ONLY AFTER the app is redeployed with SUPABASE_KEY set to the
-- project's service_role key (Project Settings > API). The server then bypasses RLS, and this script
-- closes the tables to anyone holding the public anon key (which used to be committed in app.py).
-- Until the redeploy, the live app still uses the anon key and would stop working.
do $$
declare t text; p record;
begin
  foreach t in array array['members','trainers','payments','checkins','classes','enrollments',
                           'one_day_passes','trainer_sessions','workout_logs','bmi_history']
  loop
    for p in select policyname from pg_policies where schemaname = 'public' and tablename = t loop
      execute format('drop policy %I on public.%I', p.policyname, t);
    end loop;
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
-- Check afterwards: select tablename, policyname from pg_policies where schemaname = 'public';
-- (no rows for these tables), and that the app still lists members when logged in as admin.
