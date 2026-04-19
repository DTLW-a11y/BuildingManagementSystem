import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import Dashboard from './views/Dashboard.vue'
import DataManage from './views/DataManage.vue'
import Query from './views/Query.vue'
import Statistics from './views/Statistics.vue'
import Chat from './views/Chat.vue'
import './style.css'

const routes = [
  { path: '/', redirect: '/dashboard' },
  { path: '/dashboard', component: Dashboard },
  { path: '/data', component: DataManage },
  { path: '/query', component: Query },
  { path: '/statistics', component: Statistics },
  { path: '/chat', component: Chat },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

createApp(App).use(router).mount('#app')

import DayNightToggleButton from "day-night-toggle-button"

customElements.define("toggle-button",DayNightToggleButton)