$(document).ready(function () {
    $.each($('.nav').find('li'), function() {
        $(this).toggleClass('active',
            '/' + $(this).find('a').attr('href') == window.location.pathname);
    });
});