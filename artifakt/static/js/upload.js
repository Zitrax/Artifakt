$(function () {
    $("#upload_form").submit(function (e) {
        e.preventDefault();
        // Note FormData is needed for ajax file upload
        // but it isn't supported on some older browsers.
        var formData = new FormData($(this)[0]);
        // To get the metadata as proper json format we use jquery-serialize-object.min.js
        // This currently mean that the data is duplicated in the data - however we only
        // look at the json. An alternative would be to keep the metadata in a separate form.
        var metadata = $(this).serializeJSON();
        formData.set('metadata', metadata);
        $.ajax({
            xhr: function () {
                var xhr = new window.XMLHttpRequest();
                xhr.upload.addEventListener("progress", function (evt) {
                    if (evt.lengthComputable) {
                        var pc = parseInt(evt.loaded / evt.total * 100);
                        $('.progress').removeClass('hidden');
                        $('.progress-bar').css('width', pc + '%').attr('aria-valuenow', pc).text(pc + '%');
                    }
                }, false);
                return xhr;
            },
            dataType: "json",
            type: $(this).attr('method'),
            url: $(this).attr('action'),
            data: formData,
            // This must be done for file upload !
            contentType: false,
            processData: false
        }).done(function (data) {
            // If only one file was uploaded we redirect to that specific artifact
            if (data.artifacts.length == 1)
                window.location.href = "/artifact/" + data.artifacts[0];
            // otherwise back to the list of all artifacts.
            // TODO: But should improve this later
            else
                window.location.href = "/artifacts";
        }).fail(function (jqXHR, textStatus, errorThrown) {
            alert("Error uploading file: " + errorThrown);
            $('.progress').addClass('hidden');
        });
    });

    $('#uploadbutton').bind("click", function () {
        var imgVal = $('#file').val();
        if (!imgVal) {
            return false;
        }
    });

    $(document).on('change', ':file', function () {
        var input = $(this),
            numFiles = input.get(0).files ? input.get(0).files.length : 1,
            label = input.val().replace(/\\/g, '/').replace(/.*\//, '');
        input.trigger('fileselect', [numFiles, label]);
    });
    $(document).ready(function () {
        $(':file').on('fileselect', function (event, numFiles, label) {

            var input = $(this).parents('.input-group').find(':text'),
                log = numFiles > 1 ? numFiles + ' files selected' : label;

            if (input.length) {
                input.val(log);
            } else {
                if (log) alert(log);
            }

        });
    });
});
