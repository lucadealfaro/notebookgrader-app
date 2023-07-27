(function(){

    // Thanks to https://stackoverflow.com/questions/10420352/converting-file-size-in-bytes-to-human-readable-string
    /**
     * Format bytes as human-readable text.
     *
     * @param bytes Number of bytes.
     * @param si True to use metric (SI) units, aka powers of 1000. False to use
     *           binary (IEC), aka powers of 1024.
     * @param dp Number of decimal places to display.
     *
     * @return Formatted string.
     */
    function humanFileSize(bytes, si=false, dp=1) {
        const thresh = si ? 1000 : 1024;

        if (Math.abs(bytes) < thresh) {
            return bytes + ' B';
        }

        const units = si
            ? ['kB', 'MB', 'GB', 'TB', 'PB', 'EB', 'ZB', 'YB']
            : ['KiB', 'MiB', 'GiB', 'TiB', 'PiB', 'EiB', 'ZiB', 'YiB'];
        let u = -1;
        const r = 10**dp;

        do {
            bytes /= thresh;
            ++u;
        } while (Math.round(Math.abs(bytes) * r) / r >= thresh && u < units.length - 1);


        return bytes.toFixed(dp) + ' ' + units[u];
    }

    var fileupload = {
        props: ['url'],
        data: null,
        methods: {},
        computed: {}
    };

    // This defines the data for fileupload.
    fileupload.data = function() {
        var data = {
            server_url: this.url, // URL in props for server callback.
            file_name: null, // File name
            file_type: null, // File type
            file_date: null, // Date when file uploaded
            file_path: null, // Path of file in GCS
            file_size: null, // Size of uploaded file
            readonly: null, // Is the file read-only?
            download_url: null, // URL to download a file
            uploading: false, // upload in progress
            deleting: false, // delete in progress
            delete_confirmation: false, // Show the delete confirmation thing.
        };
        fileupload.methods.load.call(data);
        return data;
    };

    fileupload.load = function () {
        // Loads the data from the server.
        axios.get(self.server_url)
            .then(function (r) {
                self.file_name = r.data.file_name;
                self.file_type = r.data.file_type;
                self.file_date = r.data.file_date;
                self.file_path = r.data.file_path;
                self.file_size = r.data.file_size;
                self.readonly = r.data.readonly;
                self.download_url = r.data.download_url;
            });
    };

    fileupload.computed.file_info = function () {
        let self = this;
        if (self.file_path) {
            let info = "";
            if (self.file_size) {
                info = humanFileSize(self.file_size.toString(), si=true);
            }
            if (self.file_type) {
                if (info) {
                    info += " " + self.file_type;
                } else {
                    info = self.file_type;
                }
            }
            if (info) {
                info = " (" + info + ")";
            }
            if (self.file_date) {
                let d = new Sugar.Date(self.file_date + "+00:00");
                info += ", uploaded " + d.relative();
            }
            return self.file_name + info;
        } else {
            return "";
        }
    }

    fileupload.methods.upload_file = function (event) {
        let self = this;
        if (self.readonly) {return;}
        let input = event.target;
        let file = input.files[0];
        if (file) {
            self.uploading = true;
            let file_type = file.type;
            let file_name = file.name;
            let file_size = file.size;
            // Requests the upload URL.
            axios.post(self.server_url, {
                action: "OBTAIN UPLOAD URL",
                mimetype: file_type,
                file_name: file_name
            }).then ((r) => {
                let upload_url = r.data.signed_url;
                let file_path = r.data.file_path;
                // Uploads the file, using the low-level interface.
                let req = new XMLHttpRequest();
                // We listen to the load event = the file is uploaded, and we call upload_complete.
                // That function will notify the server `of the location of the image.
                req.addEventListener("load", function () {
                    fileupload.upload_complete(self, file_name, file_type, file_size, file_path);
                });
                // TODO: if you like, add a listener for "error" to detect failure.
                req.open("PUT", upload_url, true);
                req.send(file);
            });
        }
    }

    fileupload.upload_complete = function (self, file_name, file_type, file_size, file_path) {
        // We need to let the server know that the upload was complete;
        axios.post(self.server_url, {
            action: "UPLOAD COMPLETE",
            file_name: file_name,
            file_type: file_type,
            file_path: file_path,
            file_size: file_size,
        }).then( function (r) {
            self.uploading = false;
            self.file_name = file_name;
            self.file_type = file_type;
            self.file_path = file_path;
            self.file_size = file_size;
            self.file_date = r.data.file_date;
            self.download_url = r.data.download_url;
        });
    }

    fileupload.methods.delete_file = function () {
        let self = this;
        if (self.readonly) {return;}
        if (!self.delete_confirmation) {
            // Ask for confirmation before deleting it.
            self.delete_confirmation = true;
        } else {
            // It's confirmed.
            self.delete_confirmation = false;
            self.deleting = true;
            // Obtains the delete URL.
            let file_path = self.file_path;
            axios.post(self.server_url, {
                action: "OBTAIN DELETION URL",
                file_path: file_path,
            }).then(function (r) {
                let delete_url = r.data.signed_url;
                if (delete_url) {
                    // Performs the deletion request.
                    let req = new XMLHttpRequest();
                    req.addEventListener("load", function () {
                        fileupload.deletion_complete(self);
                    });
                    // TODO: if you like, add a listener for "error" to detect failure.
                    req.open("DELETE", delete_url);
                    req.send();
                }
            });
        }
    };

    fileupload.deletion_complete = function (self, file_path) {
        // We need to notify the server that the file has been deleted on GCS.
        axios.post(self.server_url, {
            action: "DELETION COMPLETE",
            file_path: self.file_path,
        }).then (function (r) {
            // Poof, no more file.
            self.deleting =  false;
            self.file_name = null;
            self.file_type = null;
            self.file_date = null;
            self.file_path = null;
            self.download_url = null;
        })
    }

    fileupload.methods.download_file = function () {
        let self = this;
        if (self.download_url) {
            let req = new XMLHttpRequest();
            req.addEventListener("load", function () {
                fileupload.do_download(req);
            });
            req.responseType = 'blob';
            req.open("GET", self.download_url, true);
            req.send();
        }
    };

    fileupload.do_download = function (req) {
        let self = this;
        // This Machiavellic implementation is thanks to Massimo DiPierro.
        // This creates a data URL out of the file we downloaded.
        let data_url = URL.createObjectURL(req.response);
        // Let us now build an a tag, not attached to anything,
        // that looks like this:
        // <a href="my data url" download="myfile.jpg"></a>
        let a = document.createElement('a');
        a.href = data_url;
        a.download = self.file_name;
        // and let's click on it, to do the download!
        a.click();
        // we clean up our act.
        a.remove();
        URL.revokeObjectURL(data_url);
    };

    Q.register_vue_component('gcsfileupload', 'components-bulma/gcs_file_upload/gcs_file_upload.html',
        function(template) {
            fileupload.template = template.data;
            return fileupload;
        });

})();

