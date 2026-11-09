import { test, expect } from '@playwright/test';

const CALLER_EMAIL = process.env.E2E_CALLER_EMAIL || 'e2e_caller_playwright@example.com';
const CALLER_PASSWORD = process.env.E2E_CALLER_PASSWORD || 'E2ePlaywrightPassword123!';

test.describe('Caller Assigned-Lead Workspace', () => {
  test('Caller Workspace: Scoped Leads, Search, Filters, Detail Drawer, and Role Isolation', async ({ page }) => {
    // 1. Visit Login Page
    await page.goto('/login');

    // 2. Perform Caller Authentication
    const emailInput = page.locator('#login-email');
    const passwordInput = page.locator('#login-password');
    const submitBtn = page.locator('button[type="submit"]:has-text("Sign In")');

    await expect(emailInput).toBeVisible();
    await emailInput.fill(CALLER_EMAIL);
    await passwordInput.fill(CALLER_PASSWORD);
    await submitBtn.click();

    // 3. Caller Workspace Loads
    await expect(page).toHaveURL(/\/caller\/dashboard/);
    await expect(page.locator('h1:has-text("Caller Workspace")')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('table[aria-label="Assigned leads table"]')).toBeVisible();

    // 4. Verify Assigned Lead Record Appears
    await expect(page.locator('text=e2e_lead_assigned_caller_1')).toBeVisible();
    await expect(page.locator('text=Playwright Test Applicant Alpha')).toBeVisible();

    // 5. Verify Isolation: Other Caller's Lead is NEVER exposed
    const bodyContent = await page.innerText('body');
    expect(bodyContent).not.toContain('e2e_lead_other_caller_2');
    expect(bodyContent).not.toContain('Confidential Other Applicant');

    // 6. Search Functionality
    const searchInput = page.locator('#caller-search-input');
    await expect(searchInput).toBeVisible();
    await searchInput.fill('Alpha');
    await expect(page.locator('text=Playwright Test Applicant Alpha')).toBeVisible();

    // Search negative match
    await searchInput.fill('NonexistentApplicantXYZ');
    await expect(page.locator('text=No leads match the current filters on this page.')).toBeVisible();

    // Clear search
    const clearBtn = page.locator('button:has-text("Clear Filters")').first();
    await expect(clearBtn).toBeVisible();
    await clearBtn.click();
    await expect(page.locator('text=Playwright Test Applicant Alpha')).toBeVisible();

    // 7. Status & Work Type Dropdown Filtering
    const statusFilter = page.locator('#caller-status-filter');
    await expect(statusFilter).toBeVisible();
    await statusFilter.selectOption('new');
    await expect(page.locator('text=Playwright Test Applicant Alpha')).toBeVisible();

    const workTypeFilter = page.locator('#caller-work-type-filter');
    await expect(workTypeFilter).toBeVisible();
    await workTypeFilter.selectOption('salaried');
    await expect(page.locator('text=Playwright Test Applicant Alpha')).toBeVisible();

    await page.locator('button:has-text("Clear Filters")').first().click();

    // 8. Open Lead Detail Drawer
    const viewDetailsBtn = page.locator('button:has-text("View Details")').first();
    await expect(viewDetailsBtn).toBeVisible();
    await viewDetailsBtn.click();

    // Verify drawer contents
    await expect(page.locator('h3#caller-lead-drawer-title')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('div[role="dialog"] >> text=Playwright Test Applicant Alpha')).toBeVisible();
    await expect(page.locator('text=Read-Only Scope:')).toBeVisible();

    // Close drawer
    const closeDrawerBtn = page.locator('button[aria-label="Close lead details"]');
    await expect(closeDrawerBtn).toBeVisible();
    await closeDrawerBtn.click();
    await expect(page.locator('h3#caller-lead-drawer-title')).not.toBeVisible();

    // 9. Pagination Controls are Present and Accessible
    await expect(page.locator('button[aria-label="Previous page"]')).toBeVisible();
    await expect(page.locator('button[aria-label="Next page"]')).toBeVisible();

    // 10. Cross-Role Route Protection: Caller cannot access Admin or Customer routes
    await page.goto('/admin/dashboard');
    await expect(page).toHaveURL(/\/unauthorized/);
    await expect(page.locator('h1:has-text("403 - Unauthorized Access")')).toBeVisible({ timeout: 10000 });

    await page.goto('/customer/dashboard');
    await expect(page).toHaveURL(/\/unauthorized/);
    await expect(page.locator('h1:has-text("403 - Unauthorized Access")')).toBeVisible({ timeout: 10000 });
  });
});
