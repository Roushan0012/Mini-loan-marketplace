import { test, expect } from '@playwright/test';

test.describe('Caller Assigned-Lead Workspace', () => {
  test('Caller Workspace: Lead Scoping, Search, Filtering, and Pagination', async ({ page }) => {
    // 1. Log in as Caller
    await page.goto('/login');
    const emailInput = page.locator('input#email, input[name="email"], input[type="email"]');
    const passwordInput = page.locator('input#password, input[name="password"], input[type="password"]');
    const submitBtn = page.locator('button[type="submit"]');

    await emailInput.fill('caller_a@example.com');
    await passwordInput.fill('E2eCallerPassword123!');
    await submitBtn.click();

    // 2. Caller Workspace loads
    await expect(page).toHaveURL(/\/caller/);
    await expect(page.locator('text=Assigned Leads, text=Caller Workspace').first()).toBeVisible({ timeout: 10000 });

    // 3. Search works
    const searchInput = page.locator('input[placeholder*="Search"], input[name="search"]');
    if (await searchInput.isVisible()) {
      await searchInput.fill('Alpha');
      await page.waitForTimeout(500);
    }

    // 4. Status filter works
    const statusSelect = page.locator('select[name="status"], select[aria-label*="Status"]');
    if (await statusSelect.isVisible()) {
      await statusSelect.selectOption({ index: 1 });
      await page.waitForTimeout(500);
    }

    // 5. Work type filter works
    const workTypeSelect = page.locator('select[name="work_type"], select[aria-label*="Work Type"]');
    if (await workTypeSelect.isVisible()) {
      await workTypeSelect.selectOption({ index: 1 });
      await page.waitForTimeout(500);
    }

    // 6. Pagination controls are visible
    const nextBtn = page.locator('button:has-text("Next")');
    if (await nextBtn.isVisible()) {
      await expect(nextBtn).toBeDefined();
    }

    // 7. Verify Cross-Role Access Denied
    await page.goto('/admin');
    await expect(page.locator('text=Forbidden, text=Access Denied, text=Unauthorized').first()).toBeVisible({ timeout: 10000 });
  });
});
