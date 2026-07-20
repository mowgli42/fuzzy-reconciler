/**
 * Capture demo screenshots for docs/screenshots/
 * Usage: npx playwright test scripts/capture-screenshots.mjs
 * or: node with playwright chromium
 */
import { chromium } from 'playwright'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'docs', 'screenshots')
fs.mkdirSync(OUT, { recursive: true })

const BASE = process.env.DEMO_URL || 'http://127.0.0.1:5173'

async function shot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('wrote', file)
}

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(500)
  await shot(page, '01-ingestion.png')

  await page.getByRole('button', { name: 'Load Demo Data' }).click()
  await page.waitForSelector('text=Matching parameters')
  await page.waitForTimeout(400)
  await shot(page, '02-configuration.png')

  // Ensure Facility Loose if available
  const loose = page.getByRole('button', { name: 'Facility Loose' })
  if (await loose.count()) await loose.click()

  await page.getByRole('button', { name: 'Run Fuzzy Comparison' }).click()
  await page.waitForSelector('.kpis')
  await page.waitForTimeout(1200)
  await shot(page, '03-results-dashboard.png')

  // Filter temporal
  const temporal = page.getByRole('button', { name: 'Temporal' }).first()
  if (await temporal.count()) await temporal.click()
  await page.waitForTimeout(400)
  // Click first table row
  const row = page.locator('.table-wrap tbody tr').first()
  await row.click()
  await page.waitForSelector('aside.panel')
  await page.waitForTimeout(500)
  await shot(page, '04-detail-temporal.png')

  // Clear temporal filter, open spatial
  if (await temporal.count()) await temporal.click()
  const spatial = page.getByRole('button', { name: 'Spatial' }).first()
  if (await spatial.count()) await spatial.click()
  await page.waitForTimeout(300)
  await page.locator('.table-wrap tbody tr').first().click()
  await page.waitForTimeout(600)
  await shot(page, '05-detail-spatial.png')

  // Confirm a match for master
  await page.getByRole('button', { name: 'Confirm Match' }).click()
  await page.waitForTimeout(300)
  await page.getByRole('button', { name: 'Master (1)' }).click()
  await page.waitForTimeout(400)
  await shot(page, '06-reconciled-master.png')

  // Map zoom shot — back to results with spatial filter
  await page.getByRole('button', { name: '← Results' }).click()
  await page.waitForTimeout(800)
  await shot(page, '07-map-spatial-filter.png')

  await browser.close()
  console.log('Done')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
