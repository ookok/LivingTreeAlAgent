/**
 * Vue.js 主入口文件
 */

import { createApp } from 'vue';
import App from './App.vue';

const app = createApp(App);

app.mount('#app');

export { app };