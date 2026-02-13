import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Tasks from '../views/Tasks.vue'
import Conflicts from '../views/Conflicts.vue'
import Settings from '../views/Settings.vue'
import Logs from '../views/Logs.vue'
import Library from '../views/Library.vue'
import PasswordVault from '../views/PasswordVault.vue'
import ExistingFolders from '../views/ExistingFolders.vue'

const routes = [
  {
    path: '/',
    name: 'Dashboard',
    component: Dashboard
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: Tasks
  },
  {
    path: '/conflicts',
    name: 'Conflicts',
    component: Conflicts
  },
  {
    path: '/library',
    name: 'Library',
    component: Library
  },
  {
    path: '/passwords',
    name: 'PasswordVault',
    component: PasswordVault
  },
  {
    path: '/existing-folders',
    name: 'ExistingFolders',
    component: ExistingFolders
  },
  {
    path: '/settings',
    name: 'Settings',
    component: Settings
  },
  {
    path: '/logs',
    name: 'Logs',
    component: Logs
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
