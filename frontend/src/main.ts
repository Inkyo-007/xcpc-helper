import { createApp } from 'vue'
import App from './app/App.vue'
import { router } from './app/router'
import './shared/styles/main.css'
import './shared/styles/paper.css'

createApp(App).use(router).mount('#app')
