import { expect, test, type Page } from '@playwright/test'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

test.use({ trace: 'on', screenshot: 'on' })

const output = resolve('../backend/.runtime/validation001')
const approvedStyle = '批准用：话少，先观察再回答。'
const draftStyle = '草稿不得使用：连续长篇讲话。'
const names = [
  'Project opens', 'Chapter opens', 'WritingProfile works', 'Character page works',
  'CharacterBehaviorProfile view works', 'Draft Profile excluded from Agent Context',
  'Approved Profile visible', 'Ordinary UI hides Creative Candidates',
  'Debug shows Creative Candidates', 'Debug shows exact Character Profile used',
  'Revision Version Selector works', 'Human Feedback works', 'Memory Confirmation works',
]

async function get(page: Page, path: string) {
  const response = await page.request.get('/api/v1' + path)
  expect(response.ok(), path).toBeTruthy()
  return response.json()
}

test('VALIDATION-001 all 13 frontend smoke contracts on guarded isolated Mock host', async ({ page }, info) => {
  test.setTimeout(180000)
  await mkdir(output, { recursive: true })
  const evidence: Record<string, unknown> = {
    baseline: 'current product working tree', real_ai_behavior: 'NOT RUN', real_provider_calls: 0,
    host: '127.0.0.1:5174 proxy to isolated _test Mock host 127.0.0.1:8011',
    checks: names.map((name, index) => ({ id: index + 1, name, result: 'NOT_RUN' })),
    ui_console_errors: [], forbidden_browser_requests: [], contexts: [],
  }
  const checks = evidence.checks as { id: number; name: string; result: string; detail?: unknown }[]
  const contexts = evidence.contexts as unknown[]
  const consoleErrors = evidence.ui_console_errors as string[]
  const forbidden = evidence.forbidden_browser_requests as string[]
  const pass = (id: number, detail: unknown) => Object.assign(checks[id - 1]!, { result: 'PASS', detail })
  page.on('pageerror', error => consoleErrors.push(error.message))
  await page.route('**/*', route => {
    const url = new URL(route.request().url())
    if (!['127.0.0.1', 'localhost', '[::1]'].includes(url.hostname)) {
      forbidden.push(url.origin)
      return route.abort('blockedbyclient')
    }
    return route.continue()
  })
  try {
    await page.goto('/')
    await page.getByText('＋ 新建项目', { exact: true }).click()
    await page.getByLabel('项目名称', { exact: true }).fill(`VALIDATION-001 browser ${Date.now()}`)
    await page.getByRole('button', { name: '创建项目', exact: true }).click()
    await expect(page.locator('#project')).not.toHaveValue('')
    const project = await page.locator('#project').inputValue()
    evidence.project_id = project
    pass(1, { project_id: project, selector_value: project })

    await page.getByRole('button', { name: '写作偏好', exact: true }).click()
    await page.getByText('编辑', { exact: true }).click()
    await page.getByLabel('叙事人称').selectOption('THIRD_PERSON')
    await page.getByRole('button', { name: '保存新版本', exact: true }).click()
    await page.getByRole('button', { name: '批准 Profile v1', exact: true }).click()
    await expect(page.getByText('当前 v1 · 已批准 v1', { exact: true })).toBeVisible()
    const writingProfile = (await get(page, `/projects/${project}/writing-profile`)).approved
    expect(writingProfile.narrative_perspective).toBe('THIRD_PERSON')
    pass(3, { writing_profile_id: writingProfile.id, version: writingProfile.version, profile_hash: writingProfile.profile_hash })
    await page.screenshot({ path: resolve(output, 'frontend-writing-profile.png'), fullPage: true })
    await page.getByRole('button', { name: '关闭', exact: true }).click()

    await page.getByRole('button', { name: '人物表现', exact: true }).click()
    await expect(page.getByRole('heading', { name: '人物表现', exact: true })).toBeVisible()
    await page.locator('.character-create > summary').click()
    await page.getByLabel('姓名', { exact: true }).fill('林舟')
    await page.getByLabel('别名（每行一个，可留空）', { exact: true }).fill('舟')
    await page.getByRole('button', { name: '添加人物', exact: true }).click()
    await expect(page.locator('.character-identity')).toContainText('林舟')
    await expect(page.locator('.character-current-state')).toContainText('尚无已确认的人物状态')
    const character = await page.locator('#profile-character').inputValue()
    pass(4, { character_id: character, identity_name: '林舟', identity_separate_from_behavior: true })
    await page.getByLabel('表达方式', { exact: true }).fill(approvedStyle)
    await page.getByRole('button', { name: '保存新草稿版本', exact: true }).click()
    await page.getByRole('button', { name: '批准人物表现 v1', exact: true }).click()
    await expect(page.getByText('当前 v1 · 已批准 v1', { exact: true })).toBeVisible()
    const profilePath = `/projects/${project}/characters/${character}/behavior-profile`
    const approved = (await get(page, profilePath)).approved
    expect(approved.communication_style).toBe(approvedStyle)
    pass(5, { id: approved.id, logical_id: approved.logical_id, version: approved.version, authority: approved.authority_level })
    await page.locator('.character-edit > summary').click()
    await page.getByLabel('表达方式', { exact: true }).fill(draftStyle)
    await page.getByRole('button', { name: '保存新草稿版本', exact: true }).click()
    await expect(page.getByText('当前 v2 · 已批准 v1', { exact: true })).toBeVisible()
    await expect(page.getByTestId('character-profile-summary')).toContainText(approvedStyle)
    await expect(page.getByTestId('character-profile-summary')).not.toContainText(draftStyle)
    const split = await get(page, profilePath)
    expect(split.current.status).toBe('DRAFT')
    expect(split.current.version).toBe(2)
    expect(split.approved.id).toBe(approved.id)
    pass(7, { current_draft_id: split.current.id, current_version: 2, approved_id: approved.id, approved_version: 1, summary_displays_approved: true })
    await page.screenshot({ path: resolve(output, 'frontend-character-profile-v1-approved-v2-draft.png'), fullPage: true })
    await page.getByRole('button', { name: '关闭', exact: true }).click()

    await page.getByText('＋ 新建章节', { exact: true }).click()
    await page.getByLabel('章节标题', { exact: true }).fill('VALIDATION-001 雨夜来信')
    await page.getByRole('button', { name: '创建章节', exact: true }).click()
    await expect(page.getByRole('heading', { name: 'VALIDATION-001 雨夜来信', exact: true })).toBeVisible()
    const chapters = await get(page, `/projects/${project}/chapters`)
    const chapter = chapters[0].id as string
    evidence.chapter_id = chapter
    pass(2, { chapter_id: chapter, title_visible: true })
    await page.getByLabel('章节需求', { exact: true }).fill('[E2E:EXPLORATION][E2E:REVISION] 林舟与阿岚在雨夜会合，约定沿河寻找失落的信件。不要新增核心能力。')
    await page.getByRole('button', { name: '生成方案', exact: true }).click()
    await expect(page.getByTestId('human-gate')).toBeVisible()
    const workflow = (await get(page, `/projects/${project}/chapters/${chapter}/workflows`))[0].id as string
    evidence.workflow_id = workflow
    await expect(page.locator('main')).not.toContainText('selected_candidate_id')
    await expect(page.locator('main')).not.toContainText('Creative Exploration')
    await expect(page.locator('main')).not.toContainText('Selected Candidate')
    await expect(page.locator('main')).not.toContainText('conflict_engine')
    pass(8, { human_plan_gate_visible: true, candidate_fields_absent_from_main: true })
    await page.screenshot({ path: resolve(output, 'frontend-ordinary-plan-hides-candidates.png'), fullPage: true })

    const tasks = await get(page, `/workflows/${workflow}/agent-tasks`)
    const exploreTask = tasks.find((task: { task_type: string }) => task.task_type === 'EXPLORE_CHAPTER_CONCEPTS')
    expect(exploreTask).toBeTruthy()
    const exploreRuns = await get(page, `/agent-tasks/${exploreTask.task_id}/runs`)
    const exploreRun = exploreRuns.find((run: { status: string }) => run.status === 'SUCCEEDED')
    const context = await get(page, `/agent-runs/${exploreRun.run_id}/context`)
    const profileItem = context.package.items.find((item: { selector_id: string }) => item.selector_id === 'approved-character-behavior-profiles')
    expect(profileItem).toBeTruthy()
    expect(profileItem.source_id).toBe(approved.id)
    expect(profileItem.logical_id).toBe(approved.logical_id)
    expect(profileItem.source_version).toBe(approved.version)
    expect(profileItem.authority_level).toBe(approved.authority_level)
    expect(profileItem.selected_reason).toBeTruthy()
    expect(context.package.items.some((item: { source_id: string }) => item.source_id === split.current.id)).toBeFalsy()
    expect(JSON.stringify(context.package)).not.toContain(draftStyle)
    pass(6, { approved_profile_record_id: approved.id, logical_id: approved.logical_id, source_version: profileItem.source_version, draft_v2_record_id_excluded: split.current.id, draft_sentinel_excluded: true })
    contexts.push({ task_type: exploreTask.task_type, task_id: exploreTask.task_id, run_id: exploreRun.run_id, package_id: context.package.context_package_id, profile_id: context.package.profile_id, profile_version: context.package.profile_version, used_character_profile: profileItem })

    await page.getByRole('button', { name: 'Debug', exact: true }).click()
    await page.getByText('A03 Creative Exploration', { exact: true }).click()
    const candidateTable = page.locator('#debug-section table').filter({ hasText: 'Candidate / Event' })
    await expect(candidateTable).toBeVisible()
    await expect(candidateTable.locator('tbody tr')).toHaveCount(1)
    await expect(page.locator('#debug-section')).toContainText('A7_AI_INFERENCE')
    await expect(page.locator('#debug-section')).toContainText('ContextPackage / PromptLineage')
    pass(9, { candidate_table_visible: true, mock_candidate_count: 1, candidate_is_A7: true })
    await page.screenshot({ path: resolve(output, 'frontend-debug-candidates.png'), fullPage: true })
    await page.getByText('Context / Prompt', { exact: true }).click()
    await page.locator('#debug-run').selectOption(exploreRun.run_id)
    const included = page.getByTestId('context-included-items')
    await expect(included).toContainText(approved.id)
    const usedRow = included.locator('tbody tr').filter({ hasText: approved.id })
    await expect(usedRow).toContainText(`v${approved.version}`)
    await expect(usedRow).toContainText(approved.authority_level)
    await usedRow.getByText('查看内容', { exact: true }).click()
    await expect(usedRow).toContainText(approvedStyle)
    await expect(usedRow).not.toContainText(draftStyle)
    pass(10, { exact_run_id: exploreRun.run_id, source_type: profileItem.source_type, logical_id: profileItem.logical_id, version: profileItem.source_version, authority: profileItem.authority_level, selected_reason: profileItem.selected_reason, displayed_payload_is_approved_v1: true })
    await page.screenshot({ path: resolve(output, 'frontend-debug-used-approved-profile.png'), fullPage: true })
    await page.getByRole('button', { name: '关闭', exact: true }).click()

    await page.getByRole('button', { name: '批准并开始写作', exact: true }).click()
    await expect(page.getByRole('button', { name: '根据审阅修改', exact: true })).toBeVisible()
    const original = await page.getByLabel('章节正文', { exact: true }).textContent()
    await page.getByRole('button', { name: '根据审阅修改', exact: true }).click()
    await expect(page.getByText('Review v2 · 对应 Draft v2', { exact: true })).toBeVisible()
    await expect(page.getByLabel('正文版本', { exact: true })).toHaveValue('2')
    await page.getByLabel('正文版本', { exact: true }).selectOption('1')
    await expect(page.getByLabel('章节正文', { exact: true })).toHaveText(original!)
    await expect(page.getByRole('status').filter({ hasText: '正在阅读历史正文 v1' })).toBeVisible()
    await page.getByLabel('正文版本', { exact: true }).selectOption('2')
    await expect(page.getByText('Review v2 · 对应 Draft v2', { exact: true })).toBeVisible()
    pass(11, { current_version: 2, original_v1_preserved: true, selected_v1_then_v2: true, review_exact_version_binding: true })
    await page.screenshot({ path: resolve(output, 'frontend-revision-version-selector.png'), fullPage: true })

    await page.getByRole('button', { name: '根据我的意见修改', exact: true }).click()
    const feedbackText = '林舟这里说话不像他，只调整这一处表达，其他地方不要动。'
    await page.locator('#human-feedback').fill(feedbackText)
    await page.getByRole('button', { name: '发送并修改', exact: true }).click()
    await expect(page.getByLabel('正文版本', { exact: true })).toHaveValue('3')
    await expect(page.getByText('Review v3 · 对应 Draft v3', { exact: true })).toBeVisible()
    await expect(page.getByRole('region', { name: '用户反馈修改', exact: true })).toContainText(feedbackText)
    const feedback = await get(page, `/workflows/${workflow}/feedback`)
    expect(feedback).toHaveLength(1)
    expect(feedback[0].feedback.raw_feedback).toBe(feedbackText)
    expect(feedback[0].interpretation.body.action).toBe('REVISION')
    const afterFeedback = await get(page, profilePath)
    expect(afterFeedback.current.id).toBe(split.current.id)
    expect(afterFeedback.approved.id).toBe(approved.id)
    pass(12, { feedback_id: feedback[0].feedback.id, interpreted_action: 'REVISION', resulting_draft_version: 3, character_profile_current_and_approved_unchanged: true })
    await page.screenshot({ path: resolve(output, 'frontend-human-feedback-revision.png'), fullPage: true })

    await page.getByRole('button', { name: '完成本章', exact: true }).click()
    await expect(page.getByRole('heading', { name: '本章将记住', exact: true })).toBeVisible()
    await expect(page.getByRole('button', { name: '确认并完成', exact: true })).toBeEnabled()
    const proposalHistory = await get(page, `/workflows/${workflow}/memory`)
    expect(proposalHistory[0].status).toBe('PROPOSED')
    const currentVersion = (await get(page, `/projects/${project}/chapters/${chapter}`)).current_version
    expect(proposalHistory[0].request.draft_version).toBe(currentVersion)
    await page.screenshot({ path: resolve(output, 'frontend-memory-confirmation.png'), fullPage: true })
    await page.getByRole('button', { name: '确认并完成', exact: true }).click()
    await expect(page.getByRole('heading', { name: '章节已完成。', exact: true })).toBeVisible()
    const committed = await get(page, `/workflows/${workflow}/memory`)
    const completed = await get(page, `/workflows/${workflow}`)
    expect(committed[0].status).toBe('COMMITTED')
    expect(committed[0].batch.confirmed_by).toBeTruthy()
    expect(completed.status).toBe('COMPLETED')
    const finalProfile = await get(page, profilePath)
    expect(finalProfile.current.id).toBe(split.current.id)
    expect(finalProfile.approved.id).toBe(approved.id)
    pass(13, { proposal_id: proposalHistory[0].proposal.id, source_draft_version: currentVersion, candidate_count: proposalHistory[0].proposal.candidates.length, explicit_human_confirmation: true, batch_id: committed[0].batch.id, workflow_status: completed.status, no_profile_learning: true })
    await page.screenshot({ path: resolve(output, 'frontend-chapter-completed.png'), fullPage: true })

    const finalTasks = await get(page, `/workflows/${workflow}/agent-tasks`)
    for (const task of finalTasks) {
      for (const run of await get(page, `/agent-tasks/${task.task_id}/runs`)) {
        expect(run.provider).toBe('mock')
        const runContext = await get(page, `/agent-runs/${run.run_id}/context`)
        const lineage = await get(page, `/agent-runs/${run.run_id}/prompt-lineage`)
        contexts.push({ task_type: task.task_type, task_id: task.task_id, run_id: run.run_id, provider: run.provider, context_package_id: runContext.package.context_package_id, context_profile_id: runContext.package.profile_id, context_profile_version: runContext.package.profile_version, prompt_lineage_id: lineage.lineage_id, task_template: lineage.task_template })
      }
    }
    expect(consoleErrors).toEqual([])
    expect(forbidden).toEqual([])
    expect(checks.every(check => check.result === 'PASS')).toBeTruthy()
    evidence.result = 'PASS'
  } finally {
    evidence.finished_at = new Date().toISOString()
    if (!evidence.result) evidence.result = 'FAIL_OR_INCOMPLETE'
    await writeFile(resolve(output, 'frontend-smoke.json'), JSON.stringify(evidence, null, 2) + '\n')
    await info.attach('frontend-smoke-evidence', { path: resolve(output, 'frontend-smoke.json'), contentType: 'application/json' })
  }
})
