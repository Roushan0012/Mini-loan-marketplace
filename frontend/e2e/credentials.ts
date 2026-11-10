import * as fs from 'fs';
import * as path from 'path';

export interface RoleCredentials {
  email: string;
  password: string;
}

/**
 * Attempts to parse .env.e2e.local if it exists and variables are not already in process.env.
 */
function loadLocalE2EEnvIfPresent(): void {
  const possiblePaths = [
    path.resolve(process.cwd(), '.env.e2e.local'),
    path.resolve(process.cwd(), '../.env.e2e.local'),
  ];

  for (const envPath of possiblePaths) {
    if (fs.existsSync(envPath)) {
      try {
        const content = fs.readFileSync(envPath, 'utf8');
        const lines = content.split('\n');
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || trimmed.startsWith('#')) continue;
          const eqIdx = trimmed.indexOf('=');
          if (eqIdx > 0) {
            const key = trimmed.slice(0, eqIdx).trim();
            const val = trimmed.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, '');
            if (!process.env[key] && val) {
              process.env[key] = val;
            }
          }
        }
      } catch {
        // Ignore read errors
      }
      break;
    }
  }
}

/**
 * Read and validate a required E2E credential from environment variables.
 * Fails before browser execution if absent, displaying the variable name only.
 */
export function getRequiredE2ECredential(varName: string): string {
  loadLocalE2EEnvIfPresent();
  const value = process.env[varName]?.trim();
  if (!value) {
    throw new Error(`Missing required environment variable: ${varName}`);
  }
  return value;
}

/**
 * Validate that an E2E email begins with 'e2e_' and password is >= 12 characters.
 */
export function validateRoleCredentials(
  emailVar: string,
  passwordVar: string,
  roleName: string
): RoleCredentials {
  const email = getRequiredE2ECredential(emailVar);
  const password = getRequiredE2ECredential(passwordVar);

  if (!email.toLowerCase().startsWith('e2e_')) {
    throw new Error(
      `Invalid ${emailVar}: E2E test email for role '${roleName}' must start with 'e2e_' prefix.`
    );
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    throw new Error(
      `Invalid ${emailVar}: '${email}' is not a valid email address.`
    );
  }

  if (password.length < 12) {
    throw new Error(
      `Invalid ${passwordVar}: E2E password for role '${roleName}' must have at least 12 characters.`
    );
  }

  return { email, password };
}

/**
 * Validate that credentials between roles are not accidentally identical.
 */
export function validateRolesAreDistinct(
  roles: Array<{ role: string; credentials: RoleCredentials }>
): void {
  for (let i = 0; i < roles.length; i++) {
    for (let j = i + 1; j < roles.length; j++) {
      const a = roles[i];
      const b = roles[j];

      if (a.credentials.email.toLowerCase() === b.credentials.email.toLowerCase()) {
        throw new Error(
          `Security violation: Roles '${a.role}' and '${b.role}' cannot share identical email addresses.`
        );
      }

      if (a.credentials.password === b.credentials.password) {
        throw new Error(
          `Security violation: Roles '${a.role}' and '${b.role}' cannot share identical passwords.`
        );
      }
    }
  }
}
