/**
 * Study roles: API returns `role` (label: admin | staff) and `roleCanonical` (admin | editor).
 * Staff maps to editor for permissions. Legacy viewer was migrated to editor on the server.
 */

export function canEditStudy(roleCanonical) {
  return roleCanonical === 'editor' || roleCanonical === 'admin'
}

export function isStudyAdmin(roleCanonical) {
  return roleCanonical === 'admin'
}

/** Display label for a study membership row */
export function formatStudyRoleLabel(study) {
  if (study?.role) return study.role
  if (study?.roleCanonical === 'admin') return 'admin'
  return 'staff'
}
