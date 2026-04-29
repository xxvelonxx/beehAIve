/* CayenaBot — showroom-publish.js
 * Bundle a project (multi-unit) into a self-contained ZIP showroom.
 * Implemented in next milestone. This is a stub that surfaces a clear
 * "coming soon" toast so the wiring is testable without features.
 */

export function mountShowroomPublish({ state, toast }) {
  return {
    async publishZip() {
      toast?.('Publicación ZIP en construcción — próximo milestone', 'info');
    },
    embedSnippet() {
      return '<!-- showroom embed pendiente -->';
    },
  };
}
