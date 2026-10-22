alter table public.emploi_du_temps
  add column if not exists date_jour_locale date;

update public.emploi_du_temps
set date_jour_locale = (debut at time zone 'Africa/Casablanca')::date
where date_jour_locale is null;

alter table public.emploi_du_temps
  alter column date_jour_locale set not null;

alter table public.alerte_absence
  add column if not exists debut_horaire timestamptz,
  add column if not exists fin_horaire timestamptz,
  add column if not exists activite_horaire text;

update public.alerte_absence as alert
set debut_horaire = schedule.debut,
    fin_horaire = schedule.fin,
    activite_horaire = schedule.type_activite
from public.emploi_du_temps as schedule
where schedule.id = alert.id_emploi_du_temps
  and alert.debut_horaire is null;

create unique index if not exists emploi_du_temps_personnel_jour_idx
  on public.emploi_du_temps (id_personnel, date_jour_locale);

create unique index if not exists alerte_absence_schedule_type_idx
  on public.alerte_absence (id_emploi_du_temps, type)
  where id_emploi_du_temps is not null
    and type in (
      'absence'::public.alert_type,
      'retard'::public.alert_type
    );

revoke insert, update, delete on table public.emploi_du_temps
  from anon, authenticated;

create or replace function public.upsert_personnel_schedule(
  target_personnel uuid,
  operator_user_id uuid,
  local_day date,
  starts_at timestamptz,
  ends_at timestamptz,
  activity_type text
)
returns table (
  id uuid,
  id_personnel uuid,
  date_jour_locale date,
  debut timestamptz,
  fin timestamptz,
  type_activite text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  schedule_id uuid;
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may manage schedules.';
  end if;

  if not exists (
    select 1
    from public.personnel as operator_person
    join public.acces_utilisateur as operator_role
      on operator_role.id_personnel = operator_person.id
    where operator_person.auth_user_id = operator_user_id
      and operator_person.actif
      and operator_person.acces_approuve
      and operator_role.role in (
        'rh'::public.app_role,
        'scolarite'::public.app_role
      )
      and operator_role.date_debut <= now()
      and (
        operator_role.date_fin is null
        or operator_role.date_fin > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'An active RH or Scolarité role is required.';
  end if;

  if target_personnel is null
    or local_day is null
    or starts_at is null
    or ends_at is null
    or activity_type is null
    or length(btrim(activity_type)) = 0
    or length(btrim(activity_type)) > 120
    or starts_at >= ends_at
    or (starts_at at time zone 'Africa/Casablanca')::date <> local_day
    or (ends_at at time zone 'Africa/Casablanca')::date <> local_day
  then
    raise exception using
      errcode = '22023',
      message = 'The schedule is invalid or crosses the local day boundary.';
  end if;

  if not exists (
    select 1
    from public.personnel as p
    where p.id = target_personnel
      and p.actif
  ) then
    raise exception using
      errcode = '22023',
      message = 'The personnel record is not active.';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended(target_personnel::text || ':' || local_day::text, 0)
  );

  select schedule.id
  into schedule_id
  from public.emploi_du_temps as schedule
  where schedule.id_personnel = target_personnel
    and schedule.date_jour_locale = local_day
  for update;

  if schedule_id is null then
    insert into public.emploi_du_temps as inserted_schedule (
      id_personnel,
      date_jour_locale,
      debut,
      fin,
      type_activite
    )
    values (
      target_personnel,
      local_day,
      starts_at,
      ends_at,
      btrim(activity_type)
    )
    returning inserted_schedule.id into schedule_id;
  else
    update public.emploi_du_temps as schedule
    set debut = starts_at,
        fin = ends_at,
        type_activite = btrim(activity_type)
    where schedule.id = schedule_id;

    delete from public.alerte_absence as alert
    where alert.id_emploi_du_temps = schedule_id
      and alert.type in (
        'absence'::public.alert_type,
        'retard'::public.alert_type
      )
      and alert.statut = 'envoyee'::public.alert_status;
  end if;

  return query
  select
    schedule.id,
    schedule.id_personnel,
    schedule.date_jour_locale,
    schedule.debut,
    schedule.fin,
    schedule.type_activite
  from public.emploi_du_temps as schedule
  where schedule.id = schedule_id;
end;
$$;

create or replace function public.evaluate_daily_attendance_alerts(
  target_day date,
  operator_user_id uuid,
  grace_minutes integer default 10
)
returns table (
  id uuid,
  id_personnel uuid,
  id_emploi_du_temps uuid,
  date_alerte timestamptz,
  type public.alert_type,
  statut public.alert_status,
  nom text,
  prenom text,
  debut timestamptz,
  fin timestamptz,
  type_activite text
)
language plpgsql
security definer
set search_path = ''
as $$
declare
  schedule_row record;
  first_entry timestamptz;
  alert_kind public.alert_type;
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may evaluate attendance alerts.';
  end if;

  if target_day is null
    or grace_minutes is null
    or grace_minutes < 0
    or grace_minutes > 120
  then
    raise exception using
      errcode = '22023',
      message = 'The alert evaluation parameters are invalid.';
  end if;

  if not exists (
    select 1
    from public.personnel as operator_person
    join public.acces_utilisateur as operator_role
      on operator_role.id_personnel = operator_person.id
    where operator_person.auth_user_id = operator_user_id
      and operator_person.actif
      and operator_person.acces_approuve
      and operator_role.role in (
        'rh'::public.app_role,
        'scolarite'::public.app_role
      )
      and operator_role.date_debut <= now()
      and (
        operator_role.date_fin is null
        or operator_role.date_fin > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'An active RH or Scolarité role is required.';
  end if;

  for schedule_row in
    select
      schedule.id,
      schedule.id_personnel,
      schedule.debut,
      schedule.fin,
      schedule.type_activite,
      person.nom,
      person.prenom
    from public.emploi_du_temps as schedule
    join public.personnel as person on person.id = schedule.id_personnel
    where schedule.date_jour_locale = target_day
      and person.actif
    for update of schedule
  loop
    select min(attendance.date_heure)
    into first_entry
    from public.pointage as attendance
    where attendance.id_personnel = schedule_row.id_personnel
      and attendance.type_pointage = 'entree'::public.attendance_event_type
      and attendance.date_heure >= schedule_row.debut
      and attendance.date_heure <= schedule_row.fin;

    alert_kind := null;
    if first_entry is null and now() >= schedule_row.fin then
      alert_kind := 'absence'::public.alert_type;
    elsif first_entry > schedule_row.debut
      + make_interval(mins => grace_minutes)
    then
      alert_kind := 'retard'::public.alert_type;
    end if;

    if alert_kind is not null then
      insert into public.alerte_absence (
        id_personnel,
        id_emploi_du_temps,
        date_alerte,
        type,
        statut,
        debut_horaire,
        fin_horaire,
        activite_horaire
      )
      values (
        schedule_row.id_personnel,
        schedule_row.id,
        now(),
        alert_kind,
        'envoyee'::public.alert_status,
        schedule_row.debut,
        schedule_row.fin,
        schedule_row.type_activite
      )
      on conflict (id_emploi_du_temps, type)
        where id_emploi_du_temps is not null
          and type in (
            'absence'::public.alert_type,
            'retard'::public.alert_type
          )
        do nothing;
    end if;
  end loop;

  return query
  select
    alert.id,
    alert.id_personnel,
    alert.id_emploi_du_temps,
    alert.date_alerte,
    alert.type,
    alert.statut,
    person.nom,
    person.prenom,
    coalesce(alert.debut_horaire, schedule.debut),
    coalesce(alert.fin_horaire, schedule.fin),
    coalesce(alert.activite_horaire, schedule.type_activite)
  from public.alerte_absence as alert
  join public.personnel as person on person.id = alert.id_personnel
  join public.emploi_du_temps as schedule
    on schedule.id = alert.id_emploi_du_temps
  where schedule.date_jour_locale = target_day
    and alert.type in (
      'absence'::public.alert_type,
      'retard'::public.alert_type
    )
  order by schedule.debut, person.nom, person.prenom;
end;
$$;

create or replace function public.resolve_attendance_alert(
  target_alert uuid,
  operator_user_id uuid
)
returns boolean
language plpgsql
security definer
set search_path = ''
as $$
declare
  updated_count integer;
begin
  if (select auth.role()) is distinct from 'service_role' then
    raise exception using
      errcode = '42501',
      message = 'Only the trusted service may resolve attendance alerts.';
  end if;

  if not exists (
    select 1
    from public.personnel as operator_person
    join public.acces_utilisateur as operator_role
      on operator_role.id_personnel = operator_person.id
    where operator_person.auth_user_id = operator_user_id
      and operator_person.actif
      and operator_person.acces_approuve
      and operator_role.role in (
        'rh'::public.app_role,
        'scolarite'::public.app_role
      )
      and operator_role.date_debut <= now()
      and (
        operator_role.date_fin is null
        or operator_role.date_fin > now()
      )
  ) then
    raise exception using
      errcode = '42501',
      message = 'An active RH or Scolarité role is required.';
  end if;

  update public.alerte_absence
  set statut = 'traitee'::public.alert_status
  where alerte_absence.id = target_alert
    and alerte_absence.type in (
      'absence'::public.alert_type,
      'retard'::public.alert_type
    )
    and alerte_absence.statut = 'envoyee'::public.alert_status;

  get diagnostics updated_count = row_count;
  return updated_count = 1;
end;
$$;

revoke all on function public.upsert_personnel_schedule(
  uuid,
  uuid,
  date,
  timestamptz,
  timestamptz,
  text
) from public, anon, authenticated;
grant execute on function public.upsert_personnel_schedule(
  uuid,
  uuid,
  date,
  timestamptz,
  timestamptz,
  text
) to service_role;

revoke all on function public.evaluate_daily_attendance_alerts(
  date,
  uuid,
  integer
) from public, anon, authenticated;
grant execute on function public.evaluate_daily_attendance_alerts(
  date,
  uuid,
  integer
) to service_role;

revoke all on function public.resolve_attendance_alert(uuid, uuid)
  from public, anon, authenticated;
grant execute on function public.resolve_attendance_alert(uuid, uuid)
  to service_role;
