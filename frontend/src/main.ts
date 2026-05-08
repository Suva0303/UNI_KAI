import { createApp } from "vue";
import { createPinia } from "pinia";
import { Chart, ArcElement, BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler } from "chart.js";
import { Toaster } from "vue-sonner";
import "vue-sonner/style.css";
import App from "./App.vue";
import router from "./router";
import "./style.css";

Chart.register(ArcElement, BarElement, CategoryScale, LinearScale, LineElement, PointElement, Tooltip, Legend, Filler);
Chart.defaults.color = "#333333";
Chart.defaults.borderColor = "rgba(45,45,45,0.12)";
Chart.defaults.plugins.tooltip.backgroundColor = "#FFFFF0";
Chart.defaults.plugins.tooltip.titleColor = "#2D2D2D";
Chart.defaults.plugins.tooltip.bodyColor = "#2D2D2D";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.component("AppToaster", Toaster);
app.mount("#app");
