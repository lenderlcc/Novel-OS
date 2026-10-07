import { pages, request } from './client'
import type { components } from '../types/api.generated'
import type { Task } from '../types/models'

export type Character = components['schemas']['CharacterSubjectView']
export type Behavior = components['schemas']['CharacterBehaviorProfileBody']
export type CharacterProfile = components['schemas']['CharacterProfileView']
export type CharacterProfileState = components['schemas']['CharacterProfileState']
export type CharacterState = components['schemas']['CommittedMemory']
const charactersPath = (project: string) => `/projects/${project}/characters`
const profilePath = (project: string, character: string) => `${charactersPath(project)}/${character}/behavior-profile`

export const characterProfiles = {
  characters: (project: string, signal?: AbortSignal) => pages<Character>(charactersPath(project), signal),
  createCharacter: (project: string, name: string, aliases: string[]) => request<Character>(charactersPath(project), { body: { name, aliases } }),
  currentStates: (project: string, character: string, signal?: AbortSignal) => pages<CharacterState>(`/projects/${project}/memory?subject_id=${encodeURIComponent(character)}&memory_type=CHARACTER_STATE`, signal),
  state: (project: string, character: string, signal?: AbortSignal) => request<CharacterProfileState>(profilePath(project, character), { signal }),
  versions: (project: string, character: string, signal?: AbortSignal) => pages<CharacterProfile>(`${profilePath(project, character)}/versions`, signal),
  interpretations: (project: string, character: string, signal?: AbortSignal) => pages<Task>(`${profilePath(project, character)}/interpretations`, signal),
  save: (project: string, character: string, profile: Behavior, expected_version: number) => request<CharacterProfile>(`${profilePath(project, character)}/drafts`, { body: { profile, expected_version } }),
  approve: (project: string, character: string, expected_version: number) => request<CharacterProfile>(`${profilePath(project, character)}/approve`, { body: { expected_version } }),
  interpret: (project: string, character: string, text: string, expected_version: number) => request<CharacterProfile>(`${profilePath(project, character)}/interpret`, { body: { text, expected_version }, timeoutMs: 360000 }),
}
