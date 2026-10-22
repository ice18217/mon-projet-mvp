create or replace function public.approve_personnel_access(
  target_personnel uuid,
  approved_roles public.app_role[]
)
returns void
language plpgsql
security definer
set search_path = ''
as $$
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may approve personnel access.';
  end if;

  if approved_roles is null
    or cardinality(approved_roles) = 0
    or 'admin_technique'::public.app_role = any (approved_roles)
  then
    raise exception using
      errcode = '22023',
      message = 'The requested access roles are invalid.';
  end if;

  if exists (
    select 1
    from public.acces_utilisateur
    where id_personnel = target_personnel
      and role = 'admin_technique'::public.app_role
  ) then
    raise exception using
      errcode = '42501',
      message = 'Technical administrator access is operator-managed.';
  end if;

  update public.personnel
  set acces_approuve = true
  where id = target_personnel
    and actif;

  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'The active personnel record was not found.';
  end if;

  update public.acces_utilisateur
  set date_fin = greatest(date_debut + interval '1 microsecond', now())
  where id_personnel = target_personnel
    and date_fin is null
    and role <> 'admin_technique'::public.app_role;

  insert into public.acces_utilisateur (id_personnel, role)
  select target_personnel, requested_role
  from (
    select distinct unnest(approved_roles) as requested_role
  ) as roles;
end;
$$;

revoke all on function public.approve_personnel_access(
  uuid,
  public.app_role[]
) from public, anon, authenticated;
grant execute on function public.approve_personnel_access(
  uuid,
  public.app_role[]
) to service_role;
