import case01 from '../../../evals/manual/case-01.json'
import case02 from '../../../evals/manual/case-02.json'
import case03 from '../../../evals/manual/case-03.json'
import case04 from '../../../evals/manual/case-04.json'
import case05 from '../../../evals/manual/case-05.json'

export interface ManualCase {
  id: string
  name: string
  purpose: string
  requirement: string
}

export const manualCases = [case01, case02, case03, case04, case05] as ManualCase[]
