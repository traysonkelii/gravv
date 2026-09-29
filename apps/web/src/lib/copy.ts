/* Product vocabulary. The gravity metaphor is limited to "Gravity" and "orbit"; change labels here only. */
export const copy = {
  appName: 'Gravv',
  gravity: 'Gravity',
  orbit: 'orbit',
  contacts: 'Contacts',
  avgGravity: 'Average gravity',
  dueThisWeek: 'Due this week',
  pipeline: 'Pipeline',
  notesToRemember: 'Notes to remember',
  style: 'Style',
  band: { strong: 'Strong', steady: 'Steady', weak: 'Weak', drifting: 'Drifting' } as const,
  status: {
    active: 'Active',
    follow_up: 'Follow up',
    needs_attention: 'Needs attention',
    drifting: 'Drifting',
    archived: 'Archived',
  } as const,
  nav: {
    home: 'Home',
    contacts: 'Contacts',
    network: 'Network',
    analytics: 'Analytics',
    insights: 'Insights',
    tasks: 'Tasks',
    deals: 'Deals',
    settings: 'Settings',
    capture: 'Capture',
  },
}

export type Band = keyof typeof copy.band
