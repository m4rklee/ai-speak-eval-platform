import type { Component } from 'vue'
import {
  SoundOutlined,
  CustomerServiceOutlined,
  DatabaseOutlined,
  ColumnWidthOutlined,
  ExperimentOutlined,
  AppstoreOutlined,
  TeamOutlined,
} from '@ant-design/icons-vue'

export type PageIconKey =
  | 'oral-eval'
  | 'listen-eval'
  | 'models'
  | 'side-by-side'
  | 'prompt-lab'
  | 'scenario'
  | 'user-manage'

export const PAGE_ICON_META: Record<
  PageIconKey,
  { icon: Component; color: string; bg: string }
> = {
  'oral-eval': {
    icon: SoundOutlined,
    color: '#1677ff',
    bg: 'linear-gradient(135deg, #e6f4ff 0%, #d6e8ff 100%)',
  },
  'listen-eval': {
    icon: CustomerServiceOutlined,
    color: '#722ed1',
    bg: 'linear-gradient(135deg, #f9f0ff 0%, #efdbff 100%)',
  },
  models: {
    icon: DatabaseOutlined,
    color: '#08979c',
    bg: 'linear-gradient(135deg, #e6fffb 0%, #b5f5ec 100%)',
  },
  'side-by-side': {
    icon: ColumnWidthOutlined,
    color: '#d46b08',
    bg: 'linear-gradient(135deg, #fff7e6 0%, #ffe7ba 100%)',
  },
  'prompt-lab': {
    icon: ExperimentOutlined,
    color: '#c41d7f',
    bg: 'linear-gradient(135deg, #fff0f6 0%, #ffd6e7 100%)',
  },
  scenario: {
    icon: AppstoreOutlined,
    color: '#389e0d',
    bg: 'linear-gradient(135deg, #f6ffed 0%, #d9f7be 100%)',
  },
  'user-manage': {
    icon: TeamOutlined,
    color: '#0958d9',
    bg: 'linear-gradient(135deg, #e6f4ff 0%, #bae0ff 100%)',
  },
}
