/**
 * Capture current operator UI walkthrough into docs/screenshots/
 * Requires API :8010 and Vite :5173.
 */
import { chromium } from 'playwright'
import path from 'path'
import { fileURLToPath } from 'url'
import fs from 'fs'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const ROOT = path.resolve(__dirname, '..')
const OUT = path.join(ROOT, 'docs', 'screenshots')

const BASE = process.env.DEMO_URL || 'http://127.0.0.1:5173'

const SHOTS = [
  '01-ingest-empty.png',
  '02-ingest-verified.png',
  '03-configure.png',
  '04-results.png',
  '05-candidate-disposition.png',
  '06-merge-board.png',
  '07-published.png',
]

async function shot(page, name) {
  const file = path.join(OUT, name)
  await page.screenshot({ path: file, fullPage: false })
  console.log('wrote', file)
}

async function main() {
  fs.mkdirSync(OUT, { recursive: true })
  // Remove outdated captures so docs only hold current UI
  for (const name of fs.readdirSync(OUT)) {
    if (name.endsWith('.png')) fs.unlinkSync(path.join(OUT, name))
  }

  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })
  await page.goto(BASE, { waitUntil: 'networkidle' })
  await page.waitForTimeout(400)
  await shot(page, SHOTS[0])

  await page.getByRole('button', { name: 'Load sample inventories' }).click()
  await page.waitForSelector('text=Verification')
  await page.waitForTimeout(500)
  await shot(page, SHOTS[1])

  await page.getByRole('button', { name: /Data looks correct/ }).click()
  await page.waitForSelector('text=Matching thresholds')
  await page.waitForTimeout(300)
  const loose = page.getByRole('button', { name: 'Facility Loose' })
  if (await loose.count()) await loose.click()
  await shot(page, SHOTS[2])

  await page.getByRole('button', { name: 'Run comparison' }).click()
  await page.waitForSelector('.kpis')
  await page.waitForTimeout(1200)
  await shot(page, SHOTS[3])

  const spatial = page.getByRole('button', { name: 'Spatial' }).first()
  if (await spatial.count()) await spatial.click()
  await page.locator('.table-wrap tbody tr').first().click()
  await page.waitForSelector('aside.panel')
  await page.waitForTimeout(500)
  await shot(page, SHOTS[4])

  await page.getByRole('complementary').getByRole('button', { name: 'Keep separate' }).click()
  await page.getByRole('button', { name: 'Commit keep separate' }).click()
  await page.waitForTimeout(250)
  await page.locator('.table-wrap tbody tr').nth(1).click()
  await page.getByRole('complementary').getByRole('button', { name: 'Merge', exact: true }).click()
  await page.getByRole('button', { name: 'Commit disposition' }).click()
  await page.waitForTimeout(250)

  await page.getByRole('button', { name: 'Proceed to Merge board' }).click()
  await page.waitForSelector('text=Merge board')
  await page.waitForTimeout(500)
  await shot(page, SHOTS[5])

  await page.getByRole('button', { name: 'Publish working set' }).click()
  await page.waitForSelector('text=Published')
  await page.waitForTimeout(400)
  await shot(page, SHOTS[6])

  await browser.close()
  console.log('Done —', SHOTS.length, 'screenshots')
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
