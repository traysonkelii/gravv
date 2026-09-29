-- Bring-your-own-key AI providers: each workspace stores its own provider keys, encrypted by the API with
-- APP_ENCRYPTION_KEY (AES-256-GCM). The key column is never readable by `authenticated`; only the worker decrypts.
create type ai_provider as enum ('anthropic', 'openai', 'deepgram');

create table ai_credentials (
  id            uuid primary key default gen_random_uuid(),
  workspace_id  uuid not null references workspaces(id) on delete cascade,
  provider      ai_provider not null,
  key_enc       bytea not null,
  key_hint      text not null,                 -- last four characters, for display
  model         text,                          -- optional model override
  verified_at   timestamptz,
  created_by    uuid not null references profiles(id),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  unique (workspace_id, provider)
);
create trigger trg_ai_credentials_updated_at before update on ai_credentials for each row execute function set_updated_at();

alter table ai_credentials enable row level security;
create policy ai_credentials_select on ai_credentials for select to authenticated using (is_member(workspace_id, 'admin'));
create policy ai_credentials_write on ai_credentials for all to authenticated
  using (is_member(workspace_id, 'admin')) with check (is_member(workspace_id, 'admin') and created_by = auth.uid());

-- Column privileges only bite once the table-level grant is gone (see D-005).
revoke select on ai_credentials from authenticated;
grant select (id, workspace_id, provider, key_hint, model, verified_at, created_by, created_at, updated_at) on ai_credentials to authenticated;

-- Every member may ask which providers are configured (no keys, no hints) so the capture sheet can explain itself.
create or replace function ai_providers_configured(ws uuid) returns text[]
language sql stable security definer set search_path = public, extensions as $$
  select coalesce(array_agg(provider::text order by provider), '{}')
  from ai_credentials where workspace_id = ws and is_member(ws, 'viewer')
$$;
revoke all on function ai_providers_configured(uuid) from public;
grant execute on function ai_providers_configured(uuid) to authenticated;
