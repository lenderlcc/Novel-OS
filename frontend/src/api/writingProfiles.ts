import { pages, request } from './client'
import type { components } from '../types/api.generated'

export type Preferences = components['schemas']['WritingPreferencesInput']
export type Profile = components['schemas']['WritingProfileView']
export type ProfileState = components['schemas']['WritingProfileState']
const path = (project: string) => `/projects/${project}/writing-profile`
export const writingProfiles = {
  state: (project: string, signal?: AbortSignal) => request<ProfileState>(path(project), { signal }),
  versions: (project: string, signal?: AbortSignal) => pages<Profile>(`${path(project)}/versions`, signal),
  save: (project: string, preferences: Preferences, expected_version: number) => request<Profile>(`${path(project)}/drafts`, { body: { preferences, expected_version } }),
  approve: (project: string, expected_version: number) => request<Profile>(`${path(project)}/approve`, { body: { expected_version } }),
}
