-- Demo data for local development and e2e. Users are created first by apps/api/scripts/seed_users.py
-- (auth admin API); this file references them by email. Fixed ids keep tests deterministic.
-- Every note reads like a practitioner wrote it. No placeholder text.

do $$
declare
  sarah uuid; dan uuid; priya uuid;
  org uuid := '00000000-0000-4000-8000-000000000001';
  -- companies
  co_spaceforce uuid := '00000000-0000-4000-8000-0000000000c1';
  co_army       uuid := '00000000-0000-4000-8000-0000000000c2';
  co_boeing     uuid := '00000000-0000-4000-8000-0000000000c3';
  co_lockheed   uuid := '00000000-0000-4000-8000-0000000000c4';
  co_northrop   uuid := '00000000-0000-4000-8000-0000000000c5';
  co_nasa       uuid := '00000000-0000-4000-8000-0000000000c6';
  co_techcorp   uuid := '00000000-0000-4000-8000-0000000000c7';
  -- contacts
  c_johnson  uuid := '00000000-0000-4000-8000-0000000000a1';
  c_rodriguez uuid := '00000000-0000-4000-8000-0000000000a2';
  c_martinez uuid := '00000000-0000-4000-8000-0000000000a3';
  c_wong     uuid := '00000000-0000-4000-8000-0000000000a4';
  c_chen     uuid := '00000000-0000-4000-8000-0000000000a5';
  c_liu      uuid := '00000000-0000-4000-8000-0000000000a6';
  c_williams uuid := '00000000-0000-4000-8000-0000000000a7';
  c_stevens  uuid := '00000000-0000-4000-8000-0000000000a8';
  c_brooks   uuid := '00000000-0000-4000-8000-0000000000a9';
  c_miller   uuid := '00000000-0000-4000-8000-0000000000aa';
  o_satellite uuid := '00000000-0000-4000-8000-0000000000d1';
  o_boeing    uuid := '00000000-0000-4000-8000-0000000000d2';
  sarah_personal uuid; dan_personal uuid; priya_personal uuid;
begin
  select id into sarah from profiles where email = 'sarah@demo.gravv.local';
  select id into dan   from profiles where email = 'dan@demo.gravv.local';
  select id into priya from profiles where email = 'priya@demo.gravv.local';
  if sarah is null or dan is null or priya is null then
    raise exception 'seed users missing; run apps/api/scripts/seed_users.py first';
  end if;
  if exists (select 1 from workspaces where id = org) then
    raise notice 'seed already loaded';
    return;
  end if;

  update profiles set role_title = 'Account Executive', timezone = 'America/New_York', onboarding_step = 5,
    onboarding_completed_at = now(), goals = '{"close_deals":true,"expand_network":true,"strengthen":true,"track_roi":false,"free_text":"Land the Phase 2 satellite program and keep the Space Force relationships warm."}'::jsonb
    where id = sarah;
  update profiles set role_title = 'Sales Manager', timezone = 'America/Chicago', onboarding_step = 5, onboarding_completed_at = now(),
    goals = '{"close_deals":true,"expand_network":false,"strengthen":true,"track_roi":true,"free_text":""}'::jsonb where id = dan;
  update profiles set role_title = 'Program Manager', timezone = 'America/Los_Angeles', onboarding_step = 5, onboarding_completed_at = now(),
    goals = '{"close_deals":false,"expand_network":true,"strengthen":true,"track_roi":false,"free_text":""}'::jsonb where id = priya;

  insert into user_interests (user_id, kind, value) values
    (sarah, 'professional', 'satellite programs'), (sarah, 'professional', 'government contracting'),
    (sarah, 'personal', 'pinball'), (sarah, 'personal', 'trail running'), (sarah, 'personal', 'barbecue'),
    (dan, 'professional', 'sales coaching'), (dan, 'personal', 'golf'),
    (priya, 'professional', 'program management'), (priya, 'personal', 'hiking');

  insert into workspaces (id, kind, name, slug, owner_user_id, settings) values
    (org, 'organization', 'Meridian Components', 'meridian', sarah,
     '{"default_contact_visibility":"team","default_cadence_days":30,"auto_apply_low_risk_facts":false,"require_mfa":false}'::jsonb);
  insert into memberships (workspace_id, user_id, role, status) values
    (org, sarah, 'owner', 'active'), (org, dan, 'manager', 'active'), (org, priya, 'member', 'active');
  update profiles set default_workspace_id = org where id in (sarah, dan, priya);

  insert into companies (id, workspace_id, name, domain, industry, type, created_by) values
    (co_spaceforce, org, 'Space Force', 'spaceforce.mil', 'government', 'government', sarah),
    (co_army, org, 'U.S. Army', 'army.mil', 'government', 'government', sarah),
    (co_boeing, org, 'Boeing', 'boeing.com', 'aerospace', 'client', sarah),
    (co_lockheed, org, 'Lockheed Martin', 'lockheedmartin.com', 'defense', 'partner', sarah),
    (co_northrop, org, 'Northrop Grumman', 'northropgrumman.com', 'defense', 'prospect', priya),
    (co_nasa, org, 'NASA', 'nasa.gov', 'government', 'government', priya),
    (co_techcorp, org, 'TechCorp Solutions', 'techcorp.example', 'tech', 'vendor', dan);

  insert into contacts (id, workspace_id, owner_user_id, company_id, honorific, first_name, last_name, title, emails, phones, location,
                        relationship_type, visibility, cadence_days, tags) values
    (c_johnson, org, sarah, co_spaceforce, 'Col.', 'Michael', 'Johnson', 'Program Director', '{michael.johnson@spaceforce.mil}', '{+1 719 555 0142}', 'Colorado Springs, CO', 'government', 'team', 14, '{decision-maker,satellite}'),
    (c_rodriguez, org, sarah, co_boeing, null, 'Emily', 'Rodriguez', 'Contract Manager', '{emily.rodriguez@boeing.com}', '{+1 312 555 0187}', 'Chicago, IL', 'client', 'team', 21, '{contracts}'),
    (c_martinez, org, sarah, co_lockheed, null, 'Sarah', 'Martinez', 'VP Sales', '{sarah.martinez@lockheedmartin.com}', '{}', 'Bethesda, MD', 'partner', 'team', 30, '{partner}'),
    (c_wong, org, priya, co_northrop, null, 'Lisa', 'Wong', 'VP Engineering', '{lisa.wong@northropgrumman.com}', '{}', 'Redondo Beach, CA', 'client', 'team', 30, '{engineering}'),
    (c_chen, org, sarah, co_nasa, 'Dr.', 'James', 'Chen', 'Chief Scientist', '{james.chen@nasa.gov}', '{}', 'Houston, TX', 'government', 'team', 45, '{science,introducer}'),
    (c_liu, org, dan, co_techcorp, null, 'Kevin', 'Liu', 'CTO', '{kevin.liu@techcorp.example}', '{}', 'Austin, TX', 'vendor', 'team', 60, '{vendor}'),
    (c_williams, org, sarah, co_spaceforce, 'Gen.', 'Patricia', 'Williams', 'Deputy Commander', '{patricia.williams@spaceforce.mil}', '{}', 'Colorado Springs, CO', 'government', 'team', 45, '{executive}'),
    (c_stevens, org, priya, co_army, 'Dr.', 'Robert', 'Stevens', 'Research Director', '{robert.stevens@army.mil}', '{}', 'Adelphi, MD', 'government', 'team', 60, '{research}'),
    (c_brooks, org, sarah, co_boeing, null, 'Amanda', 'Brooks', 'Program Manager', '{amanda.brooks@boeing.com}', '{}', 'Seattle, WA', 'client', 'team', 30, '{programs}'),
    (c_miller, org, dan, co_lockheed, null, 'Thomas', 'Miller', 'Director of Procurement', '{thomas.miller@lockheedmartin.com}', '{}', 'Fort Worth, TX', 'partner', 'team', 45, '{procurement}');

  insert into contact_facts (workspace_id, contact_id, category, content, source, created_by) values
    (org, c_johnson, 'preference', 'Drinks Diet Coke, never coffee', 'note', sarah),
    (org, c_johnson, 'interest', 'North Carolina style barbecue', 'note', sarah),
    (org, c_johnson, 'interest', 'Competitive pinball, plays in a league in Colorado Springs', 'voice', sarah),
    (org, c_johnson, 'communication_style', 'Direct and formal; wants the ask in the first two sentences', 'manual', sarah),
    (org, c_johnson, 'professional', 'Owns the Phase 2 satellite program budget through FY27', 'note', sarah),
    (org, c_rodriguez, 'communication_style', 'Prefers email over calls; replies within a day', 'manual', sarah),
    (org, c_rodriguez, 'family', 'Two kids in high school, both play soccer', 'note', sarah),
    (org, c_rodriguez, 'professional', 'Runs the subcontract review board for the Seattle site', 'note', sarah),
    (org, c_martinez, 'ambition', 'Wants to move from sales into corporate development', 'note', sarah),
    (org, c_martinez, 'preference', 'Likes early morning meetings, before 8am', 'manual', sarah),
    (org, c_wong, 'interest', 'Restores vintage motorcycles on weekends', 'note', priya),
    (org, c_wong, 'communication_style', 'Technical and detailed; bring data, not slides', 'manual', priya),
    (org, c_chen, 'interest', 'Amateur astronomy, has a backyard observatory', 'note', sarah),
    (org, c_chen, 'professional', 'Sits on the Space Force science advisory panel with Gen. Williams', 'note', sarah),
    (org, c_liu, 'preference', 'Vegetarian; suggest Thai or Indian for lunches', 'note', dan),
    (org, c_williams, 'communication_style', 'Brief and strategic; one-page summaries only', 'manual', sarah),
    (org, c_williams, 'professional', 'Mentored Col. Johnson earlier in his career', 'note', sarah),
    (org, c_stevens, 'interest', 'Marathon runner, ran Boston twice', 'note', priya),
    (org, c_brooks, 'professional', 'Reports to Emily Rodriguez on the subcontract', 'note', sarah),
    (org, c_miller, 'dislike', 'Dislikes surprise pricing changes late in a cycle', 'note', dan);

  -- Interactions over the last ~90 days. Sentiment values drive the score engine and the distribution charts.
  insert into interactions (workspace_id, contact_id, user_id, kind, direction, occurred_at, subject, body, summary, sentiment, sentiment_score, source) values
    -- Col. Michael Johnson: frequent, positive, recent
    (org, c_johnson, sarah, 'meeting', 'mutual', now() - interval '3 hours', 'Phase 2 program review',
      'Reviewed the Phase 2 satellite schedule with Michael. He is worried about the ground segment vendor slipping and asked whether we can absorb integration testing. He mentioned two program officers, Maj. Lisa Park and Capt. Omar Reyes, who will own the test plan. Wants a revised cost sheet before the 15th.',
      'Phase 2 review; Michael wants a revised cost sheet and named two program officers.', 'positive', 0.6, 'manual'),
    (org, c_johnson, sarah, 'email', 'inbound', now() - interval '6 days', 'Re: Cost assumptions',
      'Michael replied to the cost assumptions with three questions about the launch insurance line. Tone was constructive.',
      'Michael asked three questions on launch insurance.', 'neutral', 0.2, 'manual'),
    (org, c_johnson, sarah, 'call', 'outbound', now() - interval '13 days', 'Check-in call',
      'Twenty-minute call. Michael is pleased with the Phase 1 close-out. He said the deputy commander asked about our bench depth; suggested a briefing for Gen. Williams.',
      'Positive close-out feedback; suggested briefing Gen. Williams.', 'positive', 0.7, 'manual'),
    (org, c_johnson, sarah, 'meeting', 'mutual', now() - interval '27 days', 'Quarterly program sync',
      'Quarterly sync at Peterson. Walked through milestones. Michael pushed back on the risk register format; wants it as a one-pager.',
      'Quarterly sync; risk register needs a one-page format.', 'neutral', 0.1, 'manual'),
    (org, c_johnson, sarah, 'gift', 'outbound', now() - interval '41 days', 'Sent NC barbecue sauce set',
      'Sent the North Carolina sauce sampler after he mentioned missing home cooking. He sent a thank-you note the next day.',
      'Sent a barbecue sauce sampler; well received.', 'positive', 0.8, 'manual'),
    (org, c_johnson, sarah, 'email', 'outbound', now() - interval '55 days', 'Phase 1 close-out package',
      'Sent the close-out package with the lessons-learned appendix he requested.',
      'Sent Phase 1 close-out package.', 'neutral', 0.0, 'manual'),
    (org, c_johnson, sarah, 'meeting', 'mutual', now() - interval '70 days', 'Phase 1 acceptance review',
      'Acceptance review passed with two minor findings. Michael credited our integration team in front of his staff.',
      'Phase 1 accepted; public credit to our team.', 'positive', 0.9, 'manual'),
    -- Emily Rodriguez: strong, steady
    (org, c_rodriguez, sarah, 'email', 'inbound', now() - interval '1 day', 'Subcontract redlines',
      'Emily returned the subcontract redlines. Only the indemnity clause is open. She wants our counsel to call hers this week.',
      'Redlines back; indemnity clause open.', 'positive', 0.5, 'manual'),
    (org, c_rodriguez, sarah, 'meeting', 'mutual', now() - interval '9 days', 'Subcontract kickoff',
      'Kickoff with Emily and Amanda Brooks. Agreed on a 3.2M ceiling and quarterly reviews. Emily asked about our small business subcontracting plan.',
      'Kickoff done; 3.2M ceiling agreed.', 'positive', 0.7, 'manual'),
    (org, c_rodriguez, sarah, 'call', 'inbound', now() - interval '18 days', 'Pricing question',
      'Emily called about the escalation clause. Explained the index we use; she seemed satisfied.',
      'Explained the escalation index.', 'neutral', 0.3, 'manual'),
    (org, c_rodriguez, sarah, 'email', 'outbound', now() - interval '30 days', 'Draft SOW',
      'Sent the draft statement of work.', 'Sent draft SOW.', 'neutral', 0.0, 'manual'),
    (org, c_rodriguez, sarah, 'meeting', 'mutual', now() - interval '48 days', 'Site visit, Seattle',
      'Toured the Seattle site with Emily. Her kids had a soccer tournament that weekend; she was in a good mood. She flagged that the review board meets monthly.',
      'Seattle site visit; review board meets monthly.', 'positive', 0.8, 'manual'),
    (org, c_rodriguez, sarah, 'email', 'inbound', now() - interval '66 days', 'Intro from Thomas Miller',
      'Thomas Miller introduced us. Emily replied the same day and proposed a call.',
      'Introduced by Thomas Miller.', 'positive', 0.6, 'manual'),
    -- Sarah Martinez: drifting (nothing recent, declining tone)
    (org, c_martinez, sarah, 'email', 'outbound', now() - interval '68 days', 'Following up on partnership',
      'Sent a follow-up on the teaming agreement. No reply yet.',
      'Follow-up sent; no reply.', 'neutral', -0.1, 'manual'),
    (org, c_martinez, sarah, 'call', 'mutual', now() - interval '82 days', 'Teaming discussion',
      'Sarah was distracted and cut the call short; said her org is being restructured and she may move to corporate development.',
      'Call cut short; restructuring at Lockheed.', 'negative', -0.4, 'manual'),
    (org, c_martinez, sarah, 'meeting', 'mutual', now() - interval '110 days', 'Partnership exploration',
      'Good first meeting on a teaming agreement for the Army radar recompete. She likes early meetings.',
      'Teaming agreement exploration.', 'positive', 0.5, 'manual'),
    -- Lisa Wong: steady
    (org, c_wong, priya, 'meeting', 'mutual', now() - interval '12 days', 'Engineering deep dive',
      'Lisa walked through their thermal requirements. She wants test data, not slides. Asked for a follow-up with our thermal lead.',
      'Thermal requirements review; wants test data.', 'positive', 0.4, 'manual'),
    (org, c_wong, priya, 'email', 'inbound', now() - interval '35 days', 'Vendor questionnaire',
      'Lisa sent the vendor questionnaire; due in three weeks.', 'Vendor questionnaire received.', 'neutral', 0.0, 'manual'),
    (org, c_wong, priya, 'event', 'mutual', now() - interval '64 days', 'Space Symposium',
      'Met Lisa at the symposium. Long chat about vintage motorcycles; she is restoring a 1974 Norton.',
      'Met at symposium; motorcycle restoration.', 'positive', 0.7, 'manual'),
    -- Dr. James Chen: strong; introducer
    (org, c_chen, sarah, 'call', 'mutual', now() - interval '5 days', 'Advisory panel update',
      'James mentioned the science advisory panel is reviewing sensor requirements next month. Offered to introduce us to the NASA program office.',
      'Panel reviewing sensor requirements; offered a NASA intro.', 'positive', 0.8, 'manual'),
    (org, c_chen, sarah, 'meeting', 'mutual', now() - interval '31 days', 'Dinner in Houston',
      'Dinner after the JSC visit. Talked about his backyard observatory and the Gen. Williams panel work.',
      'Dinner in Houston; observatory and panel talk.', 'positive', 0.9, 'manual'),
    (org, c_chen, sarah, 'email', 'outbound', now() - interval '58 days', 'Sensor whitepaper',
      'Sent the sensor whitepaper he asked for.', 'Sent sensor whitepaper.', 'neutral', 0.1, 'manual'),
    (org, c_chen, sarah, 'introduction', 'inbound', now() - interval '88 days', 'Introduced to Gen. Williams',
      'James introduced me to Gen. Patricia Williams at the panel reception.', 'Intro to Gen. Williams.', 'positive', 0.7, 'manual'),
    -- Kevin Liu: weak
    (org, c_liu, dan, 'email', 'outbound', now() - interval '50 days', 'Renewal terms',
      'Sent renewal terms for the analytics platform. No response in two weeks.', 'Renewal terms sent.', 'neutral', -0.1, 'manual'),
    (org, c_liu, dan, 'meeting', 'mutual', now() - interval '95 days', 'Vendor review lunch',
      'Lunch at the Thai place he likes. Kevin is happy with the platform but his budget is under review.',
      'Vendor lunch; budget under review.', 'mixed', 0.1, 'manual'),
    -- Gen. Patricia Williams: steady, executive
    (org, c_williams, sarah, 'meeting', 'mutual', now() - interval '20 days', 'Executive briefing',
      'One-page briefing on bench depth, per Michael Johnson. She asked two sharp questions on surge staffing and asked to be kept informed quarterly.',
      'Executive briefing; quarterly updates requested.', 'positive', 0.6, 'manual'),
    (org, c_williams, sarah, 'email', 'outbound', now() - interval '52 days', 'Briefing request',
      'Requested a 20-minute briefing slot through her aide.', 'Requested briefing slot.', 'neutral', 0.0, 'manual'),
    -- Dr. Robert Stevens: steady
    (org, c_stevens, priya, 'call', 'mutual', now() - interval '25 days', 'Radar research update',
      'Robert shared that the radar research program is getting a plus-up. He asked about our RF test range.',
      'Radar plus-up; interest in RF range.', 'positive', 0.5, 'manual'),
    (org, c_stevens, priya, 'email', 'inbound', now() - interval '60 days', 'Boston Marathon',
      'Robert sent a photo from Boston; he finished in 3:40.', 'Personal note from Boston.', 'positive', 0.6, 'manual'),
    -- Amanda Brooks: steady
    (org, c_brooks, sarah, 'meeting', 'mutual', now() - interval '9 days', 'Subcontract kickoff',
      'Amanda will run the day-to-day on the Boeing subcontract. She wants weekly status by email.',
      'Amanda runs day-to-day; weekly email status.', 'positive', 0.5, 'manual'),
    (org, c_brooks, sarah, 'email', 'inbound', now() - interval '22 days', 'Schedule question',
      'Amanda asked whether the integration milestone can move two weeks earlier.', 'Milestone timing question.', 'neutral', 0.1, 'manual'),
    -- Thomas Miller: steady
    (org, c_miller, dan, 'call', 'mutual', now() - interval '16 days', 'Procurement calendar',
      'Thomas shared the FY procurement calendar. He warned against late pricing changes again.',
      'Procurement calendar shared.', 'neutral', 0.2, 'manual'),
    (org, c_miller, dan, 'email', 'outbound', now() - interval '44 days', 'Thanks for the Boeing intro',
      'Thanked Thomas for introducing Emily Rodriguez.', 'Thank-you for intro.', 'positive', 0.5, 'manual');

  insert into opportunities (id, workspace_id, company_id, owner_user_id, name, value_cents, stage, probability, expected_close, status) values
    (o_satellite, org, co_spaceforce, sarah, 'Phase 2 Satellite Program', 250000000, 'proposal', 60, current_date + 75, 'open'),
    (o_boeing, org, co_boeing, sarah, 'Boeing subcontract', 320000000, 'negotiation', 75, current_date + 30, 'open');
  insert into opportunity_contacts (opportunity_id, contact_id, role) values
    (o_satellite, c_johnson, 'decision_maker'), (o_satellite, c_williams, 'influencer'),
    (o_boeing, c_rodriguez, 'decision_maker'), (o_boeing, c_brooks, 'champion'), (o_boeing, c_miller, 'influencer');

  insert into tasks (workspace_id, assignee_user_id, contact_id, title, due_at, status, priority, source, created_by) values
    (org, sarah, c_johnson, 'Send revised Phase 2 cost sheet', now() + interval '2 days', 'open', 1, 'manual', sarah),
    (org, sarah, c_johnson, 'Contact the program officers Michael mentioned', now() + interval '7 days', 'open', 2, 'voice', sarah),
    (org, sarah, c_martinez, 'Re-engage Sarah Martinez on the teaming agreement', now() - interval '9 days', 'open', 1, 'manual', sarah),
    (org, sarah, c_rodriguez, 'Have counsel call Boeing legal on indemnity', now() + interval '3 days', 'open', 1, 'manual', sarah),
    (org, priya, c_wong, 'Schedule thermal lead follow-up with Lisa Wong', now() - interval '2 days', 'open', 2, 'manual', priya),
    (org, priya, c_wong, 'Return Northrop vendor questionnaire', now() + interval '5 days', 'open', 2, 'manual', priya),
    (org, dan, c_liu, 'Chase Kevin Liu on renewal terms', now() - interval '20 days', 'open', 3, 'manual', dan),
    (org, sarah, c_williams, 'Quarterly update for Gen. Williams', now() + interval '40 days', 'open', 2, 'manual', sarah),
    (org, sarah, c_chen, 'Ask James for the NASA program office intro', now() + interval '4 days', 'open', 2, 'manual', sarah),
    (org, sarah, c_rodriguez, 'Send small business subcontracting plan', now() - interval '12 days', 'done', 2, 'manual', sarah);
  update tasks set completed_at = now() - interval '11 days' where status = 'done';

  -- Graph edges match the network mockup (canonical order a < b enforced by the check constraint).
  insert into contact_edges (workspace_id, contact_a_id, contact_b_id, kind, strength, created_by)
  select org, least(a, b), greatest(a, b), k::edge_kind, s, sarah from (values
    (c_johnson, c_williams, 'reports_to', 80), (c_johnson, c_chen, 'knows', 70), (c_chen, c_williams, 'works_with', 75),
    (c_rodriguez, c_brooks, 'works_with', 85), (c_rodriguez, c_miller, 'introduced_by', 60), (c_miller, c_martinez, 'works_with', 65),
    (c_martinez, c_wong, 'former_colleague', 40), (c_stevens, c_chen, 'knows', 50), (c_liu, c_wong, 'knows', 30),
    (c_stevens, c_williams, 'knows', 45)
  ) as v(a, b, k, s);

  -- Personal workspaces: two private contacts each.
  select default_workspace_id into sarah_personal from profiles where id = sarah;
  select w.id into sarah_personal from workspaces w where w.owner_user_id = sarah and w.kind = 'personal';
  select w.id into dan_personal from workspaces w where w.owner_user_id = dan and w.kind = 'personal';
  select w.id into priya_personal from workspaces w where w.owner_user_id = priya and w.kind = 'personal';
  insert into contacts (workspace_id, owner_user_id, first_name, last_name, title, relationship_type, visibility, cadence_days) values
    (sarah_personal, sarah, 'Maya', 'Delgado', 'Former manager, now at Anduril', 'colleague', 'private', 60),
    (sarah_personal, sarah, 'Ben', 'Okoro', 'College roommate, venture investor', 'other', 'private', 90),
    (dan_personal, dan, 'Rachel', 'Kim', 'Golf partner, CFO at a supplier', 'other', 'private', 45),
    (dan_personal, dan, 'Luis', 'Ferreira', 'Former colleague', 'colleague', 'private', 90),
    (priya_personal, priya, 'Anita', 'Rao', 'Hiking group, works at JPL', 'other', 'private', 60),
    (priya_personal, priya, 'Sam', 'Whitfield', 'Mentor', 'colleague', 'private', 90);
end $$;
