-- Private buckets; object paths are <workspace_id>/<user_id>/<uuid>.<ext>.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types) values
  ('voice-notes', 'voice-notes', false, 26214400, array['audio/webm', 'audio/mp4', 'audio/mpeg', 'audio/wav']),
  ('exports', 'exports', false, null, array['application/zip']),
  ('avatars', 'avatars', false, 2097152, array['image/png', 'image/jpeg', 'image/webp'])
on conflict (id) do nothing;

create policy storage_objects_own_rw on storage.objects for all to authenticated
using (
  bucket_id in ('voice-notes', 'exports', 'avatars')
  and (storage.foldername(name))[2] = auth.uid()::text
  and exists (select 1 from public.memberships m where m.user_id = auth.uid() and m.status = 'active'
              and m.workspace_id::text = (storage.foldername(name))[1])
)
with check (
  bucket_id in ('voice-notes', 'exports', 'avatars')
  and (storage.foldername(name))[2] = auth.uid()::text
  and exists (select 1 from public.memberships m where m.user_id = auth.uid() and m.status = 'active'
              and m.workspace_id::text = (storage.foldername(name))[1])
);

create policy storage_objects_manager_read on storage.objects for select to authenticated
using (
  bucket_id in ('voice-notes', 'exports', 'avatars')
  and exists (select 1 from public.memberships m where m.user_id = auth.uid() and m.status = 'active'
              and public.role_rank(m.role) >= public.role_rank('manager')
              and m.workspace_id::text = (storage.foldername(name))[1])
);
