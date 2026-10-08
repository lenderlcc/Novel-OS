import { expect, test, type Page } from '@playwright/test'
import { writeFile } from 'node:fs/promises'

const raw = '两人在雨夜会合，约定沿河寻找失落的信件。不要新增核心能力。'
async function createAndStart(page: Page, requirement = raw, loadCase = false) {
  await page.goto('/')
  await page.getByText('＋ 新建项目', { exact: true }).click()
  await page.getByLabel('项目名称', { exact: true }).fill(`Browser ${Date.now()}`)
  await page.getByRole('button', { name: '创建项目', exact: true }).click()
  await expect(page.locator('#project')).not.toHaveValue('')
  await page.getByText('＋ 新建章节', { exact: true }).click()
  await page.getByLabel('章节标题', { exact: true }).fill('雨夜来信')
  await page.getByRole('button', { name: '创建章节', exact: true }).click()
  await expect(page.getByRole('heading', { name: '雨夜来信' })).toBeVisible()
  if (loadCase) {
    await page.getByRole('button', { name: '测试', exact: true }).click()
    await page.locator('.case-item').first().getByRole('button', { name: '载入需求' }).click()
    await expect(page.getByLabel('章节需求')).toHaveValue(/核心目标是让两个人原本比较紧张的关系出现一点缓和/)
  } else await page.getByLabel('章节需求').fill(requirement)
  await page.getByRole('button', { name: '生成方案', exact: true }).click()
}
async function ids(page: Page) {
  const project = await page.locator('#project').inputValue()
  const chapters = await (await page.request.get(`/api/v1/projects/${project}/chapters`)).json()
  const chapter = chapters[0].id as string
  const workflows = await (await page.request.get(`/api/v1/projects/${project}/chapters/${chapter}/workflows`)).json()
  return { project, chapter, workflow: workflows[0].id as string }
}
async function ready(page: Page) {
  await expect(page.getByTestId('human-gate')).toBeVisible()
  await expect(page.getByTestId('brief')).toContainText('AI 对需求的理解')
  await expect(page.getByTestId('plan-review')).toContainText('通过')
  await expect(page.getByRole('heading', { name: '章节方案' })).toBeVisible()
}
async function approve(page: Page) {
  await page.getByRole('button', { name: '批准并开始写作' }).click()
  await expect(page.getByTestId('draft')).toBeVisible()
  await expect(page.getByTestId('draft')).toContainText('Draft v1 · DRAFT')
}

 test('Case 01: load natural language → approval → Writing → reader, evaluation and exact lineage', async ({ page }) => {
  const posts: string[] = []
  page.on('request', request => { if (request.method() === 'POST') posts.push(new URL(request.url()).pathname) })
  await createAndStart(page, raw, true); await ready(page)
  await expect(page.locator('main')).not.toContainText(/[0-9a-f]{8}-[0-9a-f]{4}-/)
  await approve(page)
  const { project, chapter, workflow } = await ids(page)
  expect(await page.evaluate(id => localStorage.getItem(`novel-os.manual-case.workflow.${id}`), workflow)).toBe('case-01')
  await expect(page.getByRole('button', { name: '测试', exact: true })).toBeDisabled()
  await page.getByRole('button', { name: '人工评价' }).click()
  await expect(page.locator('main')).toHaveAttribute('inert', '')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('heading', { name: '人工评价' })).toHaveCount(0)
  await expect(page.locator('main')).not.toHaveAttribute('inert', '')
  await page.getByRole('button', { name: '人工评价' }).click()
  await page.locator('input[name="understanding"][value="GOOD"]').check()
  await page.locator('input[name="planning"][value="GOOD"]').check()
  await page.locator('input[name="audience"][value="OK"]').check()
  await page.locator('input[name="ai-feel"][value="LOW"]').check()
  await page.locator('input[name="overall"][value="ACCEPT"]').check()
  const download = page.waitForEvent('download')
  await page.getByRole('button', { name: '导出评价 JSON' }).click()
  expect((await download).suggestedFilename()).toBe('case-01-draft-v1-evaluation.json')
  await page.getByRole('button', { name: '关闭' }).click()
  await page.getByRole('button', { name: 'Debug', exact: true }).click()
  await expect(page.locator('#debug-run')).not.toHaveValue('')
  await page.getByText('Context / Prompt', { exact: true }).click()
  await expect(page.getByText('Compiled Prompt Hash', { exact: true })).toBeVisible()
  await expect(page.getByText('CP-005 v5', { exact: true })).toBeVisible()
  const get = async (path: string) => { const response = await page.request.get('/api/v1' + path); expect(response.ok()).toBeTruthy(); return response.json() }
  const snapshot = {
    workflow: await get(`/workflows/${workflow}`), chapter: await get(`/projects/${project}/chapters/${chapter}`),
    gates: await get(`/workflows/${workflow}/human-gates`), brief: await get(`/workflows/${workflow}/creative-brief`),
    plans: await get(`/projects/${project}/chapters/${chapter}/plans`), history: await get(`/workflows/${workflow}/planning/history`),
    drafts: await get(`/projects/${project}/chapters/${chapter}/versions`), writing: await get(`/workflows/${workflow}/writing/history`), tasks: await get(`/workflows/${workflow}/agent-tasks`),
  }
  await writeFile(test.info().outputPath('snapshot.json'), JSON.stringify(snapshot, null, 2))
  await page.screenshot({ path: test.info().outputPath('workspace-draft.png'), fullPage: true })
  expect(posts.filter(path => path.includes('decision'))).toHaveLength(1)
  expect(posts.every(path => /^\/api\/v1\/(projects|workflows|human-gates)/.test(path))).toBeTruthy()
  expect(posts.some(path => /fake-execute|agent.*execute|versions.*approve|plans.*approve/.test(path))).toBeFalsy()
  await page.getByRole('button', { name: '关闭' }).click()
  await page.reload()
  await expect(page.locator('#project')).toHaveValue(project)
  await expect(page.getByRole('heading', { name: '雨夜来信' })).toBeVisible()
  await expect(page.getByTestId('draft')).toBeVisible()
})

test('Case 04: Modify preserves Plan v1, presents only Plan v2, then writes', async ({ page }) => {
  await createAndStart(page); await ready(page)
  const feedback = '这个方案太平，希望冲突突然一点，双方都应该有合理立场，其他方向不变。'
  await page.getByRole('button', { name: '我想修改' }).click()
  await page.getByLabel('告诉 AI 哪些地方需要调整').fill(feedback)
  const sent = page.waitForRequest(request => request.url().includes('/decision') && request.method() === 'POST')
  await page.getByRole('button', { name: '重新生成方案' }).click()
  expect((await sent).postDataJSON()).toMatchObject({ decision: 'MODIFY', reason: feedback, expected_artifact_version: 1 })
  await expect(page.getByText('方案 v2', { exact: true })).toBeVisible()
  await page.getByText('查看历史方案').click()
  await expect(page.locator('.version-list button')).toHaveCount(2)
  await page.locator('.version-list button').filter({ hasText: 'v1' }).click()
  await expect(page.getByText('方案 v1', { exact: true })).toBeVisible()
  await expect(page.getByTestId('human-gate')).toHaveCount(0)
  await page.getByRole('button', { name: '返回当前方案' }).click()
  await expect(page.getByText('方案 v2', { exact: true })).toBeVisible()
  await approve(page)
})

for (const [decision, action] of [['REQUEST_ALTERNATIVE', '换一个方案'], ['MODIFY', '我想修改']] as const) {
  test(`${decision} generates another plan through HumanGate`, async ({ page }) => {
    await createAndStart(page); await ready(page)
    await page.getByRole('button', { name: action, exact: true }).click()
    const field = page.locator('#feedback')
    await field.fill('希望第二场景的冲突更明显，保持结尾。')
    const sent = page.waitForRequest(request => request.url().includes('/decision') && request.method() === 'POST')
    await page.getByRole('button', { name: '重新生成方案' }).click()
    expect((await sent).postDataJSON().decision).toBe(decision)
    await expect(page.getByText('方案 v2', { exact: true })).toBeVisible()
  })
}

test('stale approval explains VERSION_CONFLICT once and requires refresh', async ({ page }) => {
  await createAndStart(page); await ready(page)
  const { workflow } = await ids(page)
  const state = await (await page.request.get(`/api/v1/workflows/${workflow}`)).json()
  const gates = await (await page.request.get(`/api/v1/workflows/${workflow}/human-gates`)).json()
  const gate = gates.at(-1)
  const other = await page.request.post(`/api/v1/human-gates/${gate.id}/decision`, { data: { event_id: crypto.randomUUID(), expected_state_version: state.state_version, expected_artifact_version: gate.artifact_version, decision: 'REQUEST_ALTERNATIVE', reason: '另一测试者请求替代方案' } })
  expect(other.ok()).toBeTruthy()
  let posts = 0
  page.on('request', request => { if (request.method() === 'POST' && request.url().includes('/decision')) posts++ })
  await page.getByRole('button', { name: '批准并开始写作' }).click()
  await expect(page.getByRole('alert')).toContainText('当前内容已经发生变化，请刷新页面后再操作。')
  await page.getByText('查看技术详情').click()
  await expect(page.getByRole('alert')).toContainText('VERSION_CONFLICT')
  await expect(page.getByTestId('human-gate')).toHaveCount(0)
  expect(posts).toBe(1)
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.getByText('方案 v2', { exact: true })).toBeVisible()
})

test('provider failure is actionable and AgentRun stays inside Debug', async ({ page }) => {
  await createAndStart(page, '[E2E:MODEL_FAILURE] ' + raw)
  await expect(page.getByRole('heading', { name: '流程失败', exact: true })).toBeVisible()
  await expect(page.getByRole('status')).toContainText('模型服务配置有误，请检查本机配置后重试。')
  await expect(page.getByText('MODEL_AUTH_ERROR', { exact: true })).not.toBeVisible()
  await page.getByRole('button', { name: 'Debug', exact: true }).click()
  await page.getByText('Agent', { exact: true }).click()
  await expect(page.locator('#debug-run option')).toHaveCount(2)
  await expect(page.locator('table').filter({ hasText: 'Run / Attempt' })).toContainText('MODEL_AUTH_ERROR')
  await expect(page.getByText('正在打开章节…')).toHaveCount(0)
})

test('Draft reader remains bound to its workflow while current Plan changes', async ({ page }) => {
  await createAndStart(page); await ready(page); await approve(page)
  const { project, chapter } = await ids(page)
  const next = await page.request.post(`/api/v1/projects/${project}/chapters/${chapter}/plans`, { data: { expected_version: 1, objective: '下一版草案，不应替代批准方案', required_outcome: '保持已批准正文不变' } })
  expect(next.status()).toBe(201)
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await expect(page.getByTestId('draft')).toContainText('Draft v1 · DRAFT')
  await expect(page.locator('main')).not.toContainText('下一版草案')
  await page.getByRole('button', { name: 'Debug', exact: true }).click()
  await expect(page.getByTestId('version-pointers')).toContainText('ChapterPlanv2v1')
})

test('Vite refuses access to backend configuration and parent filesystem', async ({ page }) => {
  const configPath = new URL('../../backend/config.toml', import.meta.url).pathname
  const response = await page.request.get('/@fs' + configPath)
  expect(response.status()).toBe(403)
})

test('manual case provenance is cleared after editing and does not return after chapter navigation', async ({ page }) => {
  await page.goto('/')
  await page.getByText('＋ 新建项目', { exact: true }).click()
  await page.getByLabel('项目名称', { exact: true }).fill(`Provenance ${Date.now()}`)
  await page.getByRole('button', { name: '创建项目', exact: true }).click()
  await page.getByText('＋ 新建章节', { exact: true }).click()
  await page.getByLabel('章节标题', { exact: true }).fill('来源测试一')
  await page.getByRole('button', { name: '创建章节', exact: true }).click()
  await page.getByRole('button', { name: '测试', exact: true }).click()
  await page.locator('.case-item').first().getByRole('button', { name: '载入需求' }).click()
  await expect(page.getByText('已载入 Case 01')).toBeVisible()
  await page.getByLabel('章节需求').fill('这是编辑后的自定义需求。')
  await expect(page.getByText('已载入 Case 01')).toHaveCount(0)

  await page.getByLabel('章节标题', { exact: true }).fill('来源测试二')
  await page.getByLabel('章节序号', { exact: true }).fill('2')
  await page.getByRole('button', { name: '创建章节', exact: true }).click()
  await page.getByRole('button', { name: /第 1 章/ }).click()
  await expect(page.getByLabel('章节需求')).toHaveValue('这是编辑后的自定义需求。')
  await expect(page.getByText('已载入 Case 01')).toHaveCount(0)
})

test('remembered Debug state never locks a workspace without a recoverable snapshot', async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('novel-os.debug-open', 'true')
    localStorage.setItem('novel-os.last-project', 'missing-project')
  })
  await page.goto('/')
  await expect(page.getByRole('heading', { name: '选择一个章节' })).toBeVisible()
  await expect(page.locator('main')).not.toHaveAttribute('inert', '')
  await expect(page.getByRole('dialog')).toHaveCount(0)
})
