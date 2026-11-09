import { test, expect } from '@playwright/test';

const ADMIN_EMAIL = process.env.E2E_ADMIN_EMAIL || 'e2e_admin_playwright@example.com';
const ADMIN_PASSWORD = process.env.E2E_ADMIN_PASSWORD || 'E2ePlaywrightPassword123!';
const CUSTOMER_EMAIL = process.env.E2E_CUSTOMER_EMAIL || 'e2e_customer_playwright@example.com';
const CUSTOMER_PASSWORD = process.env.E2E_CUSTOMER_PASSWORD || 'E2ePlaywrightPassword123!';

test.describe('Administrator Aggregate Analytics & Monitoring Dashboard', () => {
  test('Admin Dashboard: Metrics loading, status breakdown, refresh, zero-PII, cross-role protection, and session logout', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');

    // 2. Perform Admin Authentication
    const emailInput = page.locator('#login-email');
    const passwordInput = page.locator('#login-password');
    const submitBtn = page.locator('button[type="submit"]:has-text("Sign In")');

    await expect(emailInput).toBeVisible();
    await emailInput.fill(ADMIN_EMAIL);
    await passwordInput.fill(ADMIN_PASSWORD);
    await submitBtn.click();

    // 3. Admin Dashboard Loads
    await expect(page).toHaveURL(/\/admin\/dashboard/);
    await expect(page.locator('h1:has-text("Administrator Analytics")')).toBeVisible({ timeout: 10000 });

    // 4. Verify Platform Metric Cards & Truthful Labels
    await expect(page.locator('text=Total Leads').first()).toBeVisible();
    await expect(page.locator('text=Total Applications').first()).toBeVisible();
    await expect(page.locator('text=Total Match Runs').first()).toBeVisible();
    await expect(page.locator('text=Total Offers').first()).toBeVisible();
    await expect(page.locator('text=Total Submissions').first()).toBeVisible();
    await expect(page.locator('text=Total offer submission records across all lifecycle statuses')).toBeVisible();

    // 5. Verify Breakdown Sections & Consistency Notice
    await expect(page.locator('h2:has-text("Application Lifecycle Status Breakdown")')).toBeVisible();
    await expect(page.locator('h2:has-text("Lender Webhook Events by Processing Status")')).toBeVisible();
    await expect(page.locator('text=Reconciliation Verified:').or(page.locator('text=Application Status Discrepancy Detected'))).toBeVisible();

    // 6. Refresh Aggregate Metrics
    const refreshBtn = page.locator('button[aria-label="Refresh aggregate metrics"]');
    await expect(refreshBtn).toBeVisible();
    await refreshBtn.click();
    await expect(page.locator('h1:has-text("Administrator Analytics")')).toBeVisible();

    // 7. Strict Privacy & Zero-PII Verification
    const bodyContent = await page.innerText('body');
    expect(bodyContent).not.toContain('@example.com');
    expect(bodyContent).not.toContain('Playwright Test Applicant Alpha');
    expect(bodyContent).not.toContain('password_hash');

    // 8. Cross-Role Route Protection: Admin cannot access Customer or Caller routes
    await page.goto('/caller/dashboard');
    await expect(page).toHaveURL(/\/unauthorized/);
    await expect(page.locator('h1:has-text("403 - Unauthorized Access")')).toBeVisible({ timeout: 10000 });

    await page.goto('/customer/dashboard');
    await expect(page).toHaveURL(/\/unauthorized/);
    await expect(page.locator('h1:has-text("403 - Unauthorized Access")')).toBeVisible({ timeout: 10000 });

    // 9. Session Logout and Role Switching
    const signOutBtn = page.locator('button:has-text("Sign Out")');
    await expect(signOutBtn).toBeVisible();
    await signOutBtn.click();

    await expect(page).toHaveURL(/\/login/);

    // Re-authenticate as Customer to confirm clean role switching
    await page.fill('#login-email', CUSTOMER_EMAIL);
    await page.fill('#login-password', CUSTOMER_PASSWORD);
    await page.click('button[type="submit"]:has-text("Sign In")');

    await expect(page).toHaveURL(/\/customer\/dashboard/);
    await expect(page.locator('h1:has-text("Welcome back")')).toBeVisible({ timeout: 10000 });

    // Final clean logout
    await page.locator('button:has-text("Sign Out")').click();
    await expect(page).toHaveURL(/\/login/);
  });
});
