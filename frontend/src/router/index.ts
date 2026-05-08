import { createRouter, createWebHistory } from "vue-router";
import { useAdminAuthStore } from "../stores/adminAuth";
import AppLayout from "../layouts/AppLayout.vue";
import HomeView from "../views/public/HomeView.vue";
import AboutView from "../views/public/AboutView.vue";
import UniversitiesView from "../views/public/UniversitiesView.vue";
import DashboardView from "../views/public/DashboardView.vue";
import ArticlesView from "../views/public/ArticlesView.vue";
import ArticleDetailView from "../views/public/ArticleDetailView.vue";
import UniversityProfileView from "../views/public/UniversityProfileView.vue";
import AdminLoginView from "../views/admin/AdminLoginView.vue";
import AdminUniversitiesView from "../views/admin/AdminUniversitiesView.vue";
import AdminStudentsView from "../views/admin/AdminStudentsView.vue";
import AdminArticlesView from "../views/admin/AdminArticlesView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "",
      component: AppLayout,
      children: [
        { path: "", name: "home", component: HomeView },
        { path: "dashboard", name: "dashboard", component: DashboardView },
        { path: "universities", name: "universities", component: UniversitiesView },
        { path: "universities/:id", name: "university-profile", component: UniversityProfileView },
        { path: "articles", name: "articles", component: ArticlesView },
        { path: "articles/:id", name: "article-detail", component: ArticleDetailView },
        { path: "about", name: "about", component: AboutView },
        { path: "admin/login", name: "admin-login", component: AdminLoginView },
      ],
    },
    {
      path: "/admin",
      component: AppLayout,
      meta: { requiresAuth: true },
      children: [
        { path: "", redirect: { name: "admin-universities" } },
        { path: "universities", name: "admin-universities", component: AdminUniversitiesView },
        { path: "students", name: "admin-students", component: AdminStudentsView },
        { path: "articles", name: "admin-articles", component: AdminArticlesView },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAdminAuthStore();
  if (to.meta.requiresAuth && !auth.isAuthenticated) {
    return { name: "admin-login" };
  }
  return true;
});

export default router;
