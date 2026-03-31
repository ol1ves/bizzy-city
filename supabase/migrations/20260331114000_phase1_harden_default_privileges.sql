-- Phase 1: prevent future broad exposure via default privileges.

do $$
begin
  if exists (select 1 from pg_roles where rolname = 'postgres') then
    begin
      alter default privileges for role postgres in schema public
        revoke all on tables from anon, authenticated;
      alter default privileges for role postgres in schema public
        revoke all on sequences from anon, authenticated;
      alter default privileges for role postgres in schema public
        revoke all on functions from anon, authenticated;
    exception
      when insufficient_privilege then
        null;
    end;
  end if;

  if exists (select 1 from pg_roles where rolname = 'supabase_admin') then
    begin
      alter default privileges for role supabase_admin in schema public
        revoke all on tables from anon, authenticated;
      alter default privileges for role supabase_admin in schema public
        revoke all on sequences from anon, authenticated;
      alter default privileges for role supabase_admin in schema public
        revoke all on functions from anon, authenticated;
    exception
      when insufficient_privilege then
        null;
    end;
  end if;
end $$;
