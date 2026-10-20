// Shared sidebar. A page includes <aside class="sidebar" id="sidebar"></aside>
// and loads this file AFTER api.js. To add a page to the menu, add one line to ITEMS.

(function () {
  const ICONS = {
    search: '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    applications:
      '<path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M19 8v6M22 11h-6"/>',
    dashboard:
      '<rect x="3" y="3" width="7" height="9" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="16" width="7" height="5" rx="1"/>',
    profile: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
  };

  // roles: who sees the link. "guest" means logged out.
  // also: other pages that should highlight this link.
  const ITEMS = [
    { label: "Explore", href: "index.html", icon: "search", roles: ["guest", "candidate", "employer", "admin"], also: ["job-detail.html"] },
    { label: "Applications", href: "pages/applications.html", icon: "applications", roles: ["guest", "candidate"] },
    { label: "Profile", href: "pages/profile.html", icon: "profile", roles: ["candidate"] },
    { label: "Dashboard", href: "pages/employer.html", icon: "dashboard", roles: ["employer"], also: ["applicants.html"] },
    { label: "Admin", href: "pages/admin.html", icon: "shield", roles: ["admin"] },
  ];

  function currentRole() {
    const user = Auth.getUser();
    return user && Auth.isLoggedIn() ? user.role : "guest";
  }

  function render() {
    const el = document.getElementById("sidebar");
    if (!el) return;

    // Pages inside /pages/ need "../" to reach the site root
    const prefix = location.pathname.includes("/pages/") ? "../" : "";
    const here = location.pathname.split("/").pop() || "index.html";
    const role = currentRole();

    const links = ITEMS.filter((item) => item.roles.includes(role))
      .map((item) => {
        const file = item.href.split("/").pop();
        const isActive = file === here || (item.also || []).includes(here);
        return (
          `<a class="nav-item${isActive ? " active" : ""}" href="${prefix}${item.href}">` +
          `<svg viewBox="0 0 24 24">${ICONS[item.icon]}</svg>${item.label}</a>`
        );
      })
      .join("");

    el.innerHTML =
      `<div class="sidebar-logo"><a href="${prefix}index.html" style="text-decoration:none">` +
      `<span class="wordmark">Synapse<span>AI</span></span></a></div>` + links;
  }

  window.renderSidebar = render; // pages can call this again after login or logout
  render();
})();