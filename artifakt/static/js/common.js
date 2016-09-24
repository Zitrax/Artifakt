var entityMap = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': '&quot;',
    "'": '&#39;',
    "/": '&#x2F;'
};

function escapeHtml(string) {
    return String(string).replace(/[&<>"'\/]/g, function (s) {
        return entityMap[s];
    });
}

function linkify() {
    // First escape the existing text to avoid rendering original text as html
    var $escaped = escapeHtml($(this).text());
    // Then linkify
    var $new = $escaped.replace(/([\da-f]{6,40})/g, "<a href=\"/artifact/$1\">$1</a>");
    $(this).html($new);
}
