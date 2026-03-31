-- Follow-up hardening: remove residual broad grants on demo views and storage.objects.

revoke all privileges on table public.public_properties_demo from anon, authenticated;
revoke all privileges on table public.public_property_images_demo from anon, authenticated;
grant select on table public.public_properties_demo to anon, authenticated;
grant select on table public.public_property_images_demo to anon, authenticated;

revoke all privileges on table storage.objects from anon, authenticated;
grant select on table storage.objects to anon, authenticated;
