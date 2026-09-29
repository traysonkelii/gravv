-- Extensions, enums, and immutable helpers used by generated columns.
create extension if not exists pgcrypto with schema extensions;
create extension if not exists citext with schema extensions;
create extension if not exists pg_trgm with schema extensions;
create extension if not exists vector with schema extensions;

create type workspace_kind        as enum ('personal', 'organization');
create type workspace_role        as enum ('viewer', 'member', 'manager', 'admin', 'owner');
create type membership_status     as enum ('invited', 'active', 'departed');
create type company_type          as enum ('client', 'partner', 'vendor', 'government', 'prospect', 'other');
create type relationship_type     as enum ('client', 'partner', 'vendor', 'colleague', 'government', 'other');
create type contact_visibility    as enum ('private', 'team');
create type contact_status        as enum ('active', 'follow_up', 'needs_attention', 'drifting', 'archived');
create type fact_category         as enum ('preference', 'dislike', 'interest', 'personal', 'professional', 'communication_style', 'ambition', 'family', 'risk', 'other');
create type fact_source           as enum ('manual', 'note', 'voice', 'email', 'calendar', 'crm', 'ai');
create type interaction_kind      as enum ('note', 'meeting', 'call', 'email', 'message', 'event', 'introduction', 'gift', 'other');
create type interaction_direction as enum ('inbound', 'outbound', 'mutual');
create type interaction_source    as enum ('manual', 'voice', 'gmail', 'outlook', 'google_calendar', 'ms_calendar', 'crm', 'import');
create type ai_status             as enum ('none', 'pending', 'processed', 'failed', 'skipped');
create type task_status           as enum ('open', 'done', 'snoozed', 'cancelled');
create type task_source           as enum ('manual', 'ai', 'voice', 'cadence');
create type opportunity_status    as enum ('open', 'won', 'lost', 'on_hold');
create type opportunity_role      as enum ('decision_maker', 'influencer', 'champion', 'blocker', 'user', 'other');
create type edge_kind             as enum ('knows', 'reports_to', 'works_with', 'introduced_by', 'former_colleague', 'other');
create type insight_kind          as enum ('follow_up', 'at_risk', 'opportunity_signal', 'introduction_path', 'trend', 'briefing', 'common_ground');
create type insight_status        as enum ('new', 'seen', 'acted', 'dismissed', 'expired');
create type insight_severity      as enum ('info', 'notice', 'warning');
create type capture_status        as enum ('uploaded', 'transcribing', 'transcribed', 'extracting', 'proposed', 'confirmed', 'discarded', 'failed');
create type job_status            as enum ('queued', 'running', 'succeeded', 'failed', 'dead');
create type integration_provider  as enum ('gmail', 'outlook', 'google_calendar', 'ms_calendar', 'salesforce', 'hubspot', 'slack', 'linkedin');
create type integration_status    as enum ('connected', 'needs_reauth', 'disabled', 'error');
create type sentiment_label       as enum ('positive', 'neutral', 'negative', 'mixed');

-- array_to_string is only STABLE in Postgres; generated columns need IMMUTABLE.
create or replace function text_array_join(arr text[]) returns text
language sql immutable parallel safe as $$ select array_to_string(arr, ' ') $$;
