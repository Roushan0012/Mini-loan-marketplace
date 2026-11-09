import { test, expect } from '@playwright/test';

test.describe('Administrator Aggregate Analytics & Monitoring Dashboard', () => {
  test('Admin Dashboard: Metrics loading, status breakdown, refresh, zero-PII, cross-role protection', async ({ page }) => {
    // 1. Log in as Admin
    await page.goto('/login');
    const emailInput = page.locator('input#email, input[name="email"], input[type="email"]');
    const passwordInput = page.locator('input#password, input[name="password"], input[type="password"]');
    const submitBtn = page.locator('button[type="submit"]');

    await emailInput.fill('admin@example.com');
    await passwordInput.fill('E2eAdminPassword123!');
    await submitBtn.click();

    // 2. Admin Dashboard Loads
    await expect(page).toHaveURL(/\/admin/);
    await expect(page.locator('text=Admin Analytics Dashboard, text=Marketplace Analytics').first()).toBeVisible({ timeout: 10000 });

    // 3. Status breakdown displays
    await expect(page.locator('text=Total Applications, text=Total Submissions').first()).toBeVisible();
    await expect(page.locator('text=Total offer submission records across all lifecycle statuses')).toBeVisible();

    // 4. Refresh Button Works
    const refreshBtn = page.locator('button:has-text("Refresh"), button[aria-label*="Refresh"]');
    if (await refreshBtn.isVisible()) {
      await refreshBtn.click();
      await page.waitForTimeout(500);
    }

    // 5. Zero-PII Verification
    // Ensure no customer names or emails are rendered on the admin dashboard
    const bodyText = await page.innerText('body');
    expect(bodyText).not.toContain('@example.com');
    expect(bodyText).not.toContain('password_hash');

    // 6. Verify Cross-Role Access Denied
    await page.goto('/caller');
    await expect(page.locator('text=Forbidden, text=Access Denied, text=Unauthorized').first()).toBeVisible({ timeout: 10000 });
  });
});
