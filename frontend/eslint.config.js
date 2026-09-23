import js from '@eslint/js'
import ts from 'typescript-eslint'
import vue from 'eslint-plugin-vue'

export default ts.config(
  { ignores: ['dist/**', 'node_modules/**', 'test-results/**', 'playwright-report/**', 'src/types/api.generated.ts'] },
  js.configs.recommended, ...ts.configs.recommended, ...vue.configs['flat/essential'],
  { files: ['**/*.vue'], languageOptions: { parserOptions: { parser: ts.parser } } },
  { rules: { 'vue/multi-word-component-names': 'off', 'no-undef': 'off' } },
)
