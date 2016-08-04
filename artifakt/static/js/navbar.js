$(document).ready(function () {
    $.each($('.nav').find('li'), function () {
        $(this).toggleClass('active',
            '/' + $(this).find('a').attr('href') == window.location.pathname);
    });

    $('#search').keypress(function (e) {
        if (e.which == 13) {
            window.open("/search/" + $(this).val(), "_self")
        }
    });
});