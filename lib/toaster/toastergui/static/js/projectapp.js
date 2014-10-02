// vim: set tabstop=4 expandtab ai:
//  BitBake Toaster Implementation
//
//  Copyright (C) 2013        Intel Corporation
//
//  This program is free software; you can redistribute it and/or modify
//  it under the terms of the GNU General Public License version 2 as
//  published by the Free Software Foundation.
//
//  This program is distributed in the hope that it will be useful,
//  but WITHOUT ANY WARRANTY; without even the implied warranty of
//  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
//  GNU General Public License for more details.
//
//  You should have received a copy of the GNU General Public License along
//  with this program; if not, write to the Free Software Foundation, Inc.,
//  51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

angular_formpost = function($httpProvider) {
  // Use x-www-form-urlencoded Content-Type
  // By Ezekiel Victor, http://victorblog.com/2012/12/20/make-angularjs-http-service-behave-like-jquery-ajax/, no license, with attribution
  $httpProvider.defaults.headers.post['Content-Type'] = 'application/x-www-form-urlencoded;charset=utf-8';

  /**
   * The workhorse; converts an object to x-www-form-urlencoded serialization.
   * @param {Object} obj
   * @return {String}
   */
  var param = function(obj) {
    var query = '', name, value, fullSubName, subName, subValue, innerObj, i;

    for(name in obj) {
      value = obj[name];

      if(value instanceof Array) {
        for(i=0; i<value.length; ++i) {
          subValue = value[i];
          fullSubName = name + '[' + i + ']';
          innerObj = {};
          innerObj[fullSubName] = subValue;
          query += param(innerObj) + '&';
        }
      }
      else if(value instanceof Object) {
        for(subName in value) {
          subValue = value[subName];
          fullSubName = name + '[' + subName + ']';
          innerObj = {};
          innerObj[fullSubName] = subValue;
          query += param(innerObj) + '&';
        }
      }
      else if(value !== undefined && value !== null)
        query += encodeURIComponent(name) + '=' + encodeURIComponent(value) + '&';
    }

    return query.length ? query.substr(0, query.length - 1) : query;
  };

  // Override $http service's default transformRequest
  $httpProvider.defaults.transformRequest = [function(data) {
    return angular.isObject(data) && String(data) !== '[object File]' ? param(data) : data;
  }];
}


/**
 * Helper to execute callback on elements from array differences; useful for incremental UI updating.
 * @param  {Array} oldArray
 * @param  {Array} newArray
 * @param  {function} compareElements
 * @param  {function} onAdded
 * @param  {function} onDeleted
 *
 * no return
 */
function _diffArrays(oldArray, newArray, compareElements, onAdded, onDeleted ) {
    if (onDeleted !== undefined) {
        oldArray.filter(function (e) { var found = 0; newArray.map(function (f) { if (compareElements(e, f)) {found = 1};}); return !found;}).map(onDeleted);
    }
    if (onAdded !== undefined) {
        newArray.filter(function (e) { var found = 0; oldArray.map(function (f) { if (compareElements(e, f)) {found = 1};}); return !found;}).map(onAdded);
    }
}


var projectApp = angular.module('project', ['ui.bootstrap', 'ngCookies'],  angular_formpost);

// modify the template tag markers to prevent conflicts with Django
projectApp.config(function($interpolateProvider) {
    $interpolateProvider.startSymbol("{[");
    $interpolateProvider.endSymbol("]}");
});


// add time interval to HH:mm filter
projectApp.filter('timediff', function() {
    return function(input) {
        function pad(j) {
            if (parseInt(j) < 10) {return "0" + j}
            return j;
        }
        seconds = parseInt(input);
        minutes = Math.floor(seconds / 60);
        seconds = seconds - minutes * 60;
        hours = Math.floor(seconds / 3600);
        seconds = seconds - hours * 3600;
        return pad(hours) + ":" + pad(minutes) + ":" + pad(seconds);
    }
});


// main controller for the project page
projectApp.controller('prjCtrl', function($scope, $modal, $http, $interval, $location, $cookies, $q, $sce) {

    $scope.getSuggestions = function(type, currentValue) {
        var deffered = $q.defer();

        $http({method:"GET", url: $scope.urls.xhr_datatypeahead, params : { type: type, value: currentValue}})
            .success(function (_data) {
                if (_data.error != "ok") {
                    alert(_data.error);
                    deffered.reject(_data.error);
                }
                deffered.resolve(_data.list);
            });

        return deffered.promise;
    }

    var inXHRcall = false;

    // default handling of XHR calls that handles errors and updates commonly-used pages
    $scope._makeXHRCall = function(callparams) {
        if (inXHRcall) {
            if (callparams.data === undefined) {
                // we simply skip the data refresh calls
                console.log("race on XHR, aborted");
                return;
            } else {
                // we return a promise that we'll solve by reissuing the command later
                var delayed = $q.defer();
                console.log("race on XHR, delayed");
                $interval(function () {$scope._makeXHRCall(callparams).then(function (d) { delayed.resolve(d); });}, 100, 1);

                return delayed.promise;
            }

        }
        var deffered = $q.defer();

        if (undefined === callparams.headers) { callparams.headers = {} };
        callparams.headers['X-CSRFToken'] = $cookies.csrftoken;

        $http(callparams).success(function(_data, _status, _headers, _config) {
            if (_data.error != "ok") {
                alert("Failed XHR request (" + _status + "): " + _data.error);
                console.error("Failed XHR request: ", _data, _status, _headers, _config);
                deffered.reject(_data.error);
            }
            else {
                // TODO: update screen data if we have fields here

                if (_data.builds !== undefined) {

                    var oldbuilds = $scope.builds;
                    $scope.builds = _data.builds;

                    // identify canceled builds here, so we can display them.
                    _diffArrays(oldbuilds, $scope.builds,
                        function (e,f) { return e.id == f.id },                         // compare
                        undefined,                                                      // added
                        function (e) {                                                  // deleted
                            if (e.status == "deleted") return;
                            e.status = "deleted";
                            for (var i = 0; i < $scope.builds.length; i++)  {
                                if ($scope.builds[i].status == "queued" && $scope.builds[i].id > e.id)
                                    continue;
                                $scope.builds.splice(i, 0, e);
                                break;
                            }
                        });

                }
                if (_data.layers !== undefined) {
                    var oldlayers = $scope.layers;
                    $scope.layers = _data.layers;

                    // show added/deleted layer notifications
                    var addedLayers = [];
                    var deletedLayers = [];
                    _diffArrays( oldlayers, $scope.layers, function (e, f) { return e.id == f.id },
                        function (e) { console.log("new layer", e);addedLayers.push(e); },
                        function (e) { console.log("del layer", e);deletedLayers.push(e); });

                    if (addedLayers.length > 0) {
                        $scope.displayAlert($scope.zone2alerts, "You have added <b>"+addedLayers.length+"</b> layer" + ((addedLayers.length>1)?"s: ":": ") + addedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>" }).join(", "), "alert-info");
                    }
                    if (deletedLayers.length > 0) {
                        $scope.displayAlert($scope.zone2alerts, "You have deleted <b>"+deletedLayers.length+"</b> layer" + ((deletedLayers.length>1)?"s: ":": ") + deletedLayers.map(function (e) { return "<a href=\""+e.layerdetailurl+"\">"+e.name+"</a>" }).join(", "), "alert-info");
                    }

                }
                if (_data.targets !== undefined) {
                    $scope.targets = _data.targets;
                }
                if (_data.machine !== undefined) {
                    $scope.machine = _data.machine;
                }
                if (_data.user !== undefined) {
                    $scope.user = _data.user;
                }

                if (_data.prj !== undefined) {
                    $scope.project = _data.prj;

                    // update breadcrumb, outside the controller
                    $('#project_name').text($scope.project.name);
                }

                $scope.validateData();
                inXHRcall = false;
                deffered.resolve(_data);
            }
        }).error(function(_data, _status, _headers, _config) {
                alert("Failed HTTP XHR request (" + _status + ")" + _data);
                console.error("Failed HTTP XHR request: ", _data, _status, _headers, _config);
                inXHRcall = false;
                deffered.reject(_data.error);
        });

        return deffered.promise;
    }

    $scope.layeralert = undefined;
    // shows user alerts on invalid project data
    $scope.validateData = function () {
        if ($scope.layers.length == 0) {
            $scope.layeralert = $scope.displayAlert($scope.zone1alerts, "You need to add some layers to this project. <a href=\""+$scope.urls.layers+"\">View all layers available in Toaster</a> or <a href=\""+$scope.urls.importlayer+"\">import a layer</a>");
        } else {
            if ($scope.layeralert != undefined) {
                $scope.layeralert.close();
                $scope.layeralert = undefined;
            }
        }
    }

    $scope.targetExistingBuild = function(targets) {
        var oldTargetName = $scope.targetName;
        $scope.targetName = targets.map(function(v,i,a){return v.target}).join(' ');
        $scope.targetNamedBuild();
        $scope.targetName = oldTargetName;
    }

    $scope.targetNamedBuild = function(target) {
        if ($scope.targetName === undefined){
            alert("No target defined, please type in a target name");
            return;
        }

        $scope.sanitizeTargetName();

        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_build,
            data : {
                targets: $scope.targetName
            }
        }).then(function (data) {
            console.log("received ", data);
            $scope.targetName = undefined;
        });
    }

    $scope.sanitizeTargetName = function() {
        if (undefined === $scope.targetName) return;
        $scope.targetName = $scope.targetName.replace(/\[.*\]/, '').trim();
    }

    $scope.buildCancel = function(id) {
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_build,
            data: {
                buildCancel: id,
            }
        });
    }

    $scope.onLayerSelect = function (item, model, label) {
        $scope.layerAddId = item.id;
    }

    $scope.layerAdd = function() {

        $http({method:"GET", url: $scope.urls.xhr_datatypeahead, params : { type: "layerdeps", value: $scope.layerAddId }})
        .success(function (_data) {
             if (_data.error != "ok") {
                 alert(_data.error);
             } else {
                 if (_data.list.length > 0) {
                     // activate modal
                     var modalInstance = $modal.open({
                       templateUrl: 'dependencies_modal',
                       controller: function ($scope, $modalInstance, items, layerAddName) {
                         $scope.items =  items;
                         $scope.layerAddName = layerAddName;
                         $scope.selectedItems = (function () { s = {}; for (var i = 0; i < items.length; i++) { s[items[i].id] = true; };return s; })();

                         $scope.ok = function() {
                            console.log("scope selected is ", $scope.selectedItems);
                            $modalInstance.close(Object.keys($scope.selectedItems).filter(function (e) { return $scope.selectedItems[e];}));
                         };

                         $scope.cancel = function() {
                            $modalInstance.dismiss('cancel');
                         };

                         $scope.update = function() {
                            console.log("updated ", $scope.selectedItems);
                         };
                       },
                       resolve: {
                         items: function () {
                             return _data.list;
                         },
                         layerAddName: function () {
                             return $scope.layerAddName;
                         },
                       }
                     });

                     modalInstance.result.then(function (selectedArray) {
                         selectedArray.push($scope.layerAddId);
                         console.log("selected", selectedArray);

                         $scope._makeXHRCall({
                             method: "POST", url: $scope.urls.xhr_edit,
                             data: {
                                 layerAdd: selectedArray.join(","),
                             }
                         }).then(function () {
                             $scope.layerAddName = undefined;
                         });
                     });
                 }
                 else {
                         $scope._makeXHRCall({
                             method: "POST", url: $scope.urls.xhr_edit,
                             data: {
                                 layerAdd:  $scope.layerAddId,
                             }
                         }).then(function () {
                             $scope.layerAddName = undefined;
                         });
                 }
             }
         });
    }

    $scope.layerDel = function(id) {
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_edit,
            data: {
                layerDel: id,
            }
        });
    }


    $scope.test = function(elementid) {
        $http({method:"GET", url: $scope.urls.xhr_datatypeahead, params : { type: "versionlayers", value: $scope.projectVersion }}).
        success(function (_data) {
            if (_data.error != "ok") {
                alert (_data.error);
            }
            else {
                 if (_data.list.length > 0) {
                     // activate modal
                     var modalInstance = $modal.open({
                       templateUrl: 'change_version_modal',
                       controller: function ($scope, $modalInstance, items, releaseName) {
                         $scope.items =  items;
                         $scope.releaseName = releaseName;

                         $scope.ok = function() {
                             $modalInstance.close();
                         };

                         $scope.cancel = function() {
                             $modalInstance.dismiss('cancel');
                         };

                       },
                       resolve: {
                         items: function () {
                             return _data.list;
                         },
                         releaseName: function () {
                             return $scope.releases.filter(function (e) { if (e.id == $scope.projectVersion) return e;})[0].name;
                         },
                       }
                     });

                     modalInstance.result.then(function () { $scope.edit(elementid)});
                 } else {
                    $scope.edit(elementid);
                 }
            }
        });
    }

    $scope.edit = function(elementid) {
        var data = {};
        console.log("edit with ", elementid);
        var alertText = undefined;
        var alertZone = undefined;
        switch(elementid) {
            case '#select-machine':
                alertText = "You have changed the machine to: <b>" + $scope.machineName + "</b>";
                alertZone = $scope.zone2alerts;
                data['machineName'] = $scope.machineName;
                break;
            case '#change-project-name':
                data['projectName'] = $scope.projectName;
                alertText = "You have changed the project name to: <b>" + $scope.projectName + "</b>";
                alertZone = $scope.zone3alerts;
                break;
            case '#change-project-version':
                data['projectVersion'] = $scope.projectVersion;
                alertText = "You have changed the release to: ";
                alertZone = $scope.zone3alerts;
                break;
            default:
                throw "FIXME: implement conversion for element " + elementid;
        }

        console.log("calling edit with ", data);
        $scope._makeXHRCall({
            method: "POST", url: $scope.urls.xhr_edit, data: data,
        }).then( function () {
            $scope.toggle(elementid);
            if (data['projectVersion'] != undefined) {
                alertText += "<b>" + $scope.project.release.name + "</b>";
            }
            $scope.displayAlert(alertZone, alertText, "alert-info");
        });
    }


    $scope.executeCommands = function() {
        cmd = $location.path();

        function _cmdExecuteWithParam(param, f) {
            if (cmd.indexOf(param)==0) {
                if (cmd.indexOf("=") > -1) {
                    var parameter = cmd.split("=", 2)[1];
                    if (parameter != undefined && parameter.length > 0) {
                        f(parameter);
                    }
                } else {
                    f();
                };
            }
        }

        _cmdExecuteWithParam("/newproject", function () {
            $scope.displayAlert($scope.zone1alerts,
                    "Your project <strong>" + $scope.project.name +
                    "</strong> has been created. You can now <a href=\""+ $scope.urls.layers +
                    "\">add layers</a> and <a href=\""+ $scope.urls.targets +
                    "\">select targets</a> you want to build.", "alert-success");
        });

        _cmdExecuteWithParam("/targetbuild=", function (targets) {
            var oldTargetName = $scope.targetName;
            $scope.targetName = targets.split(",").join(" ");
            $scope.targetNamedBuild();
            $scope.targetName = oldTargetName;
        });

        _cmdExecuteWithParam("/machineselect=", function (machine) {
            $scope.machineName = machine;
            $scope.toggle('#select-machine');
        });


        _cmdExecuteWithParam("/layeradd=", function (layer) {
            angular.forEach(layer.split(","), function (l) {
                $scope.layerAddId = l;
                $scope.layerAdd();
            });
        });
    }

    $scope.displayAlert = function(zone, text, type) {
        if (zone.maxid === undefined) { zone.maxid = 0; }
        var crtid = zone.maxid ++;
        angular.forEach(zone, function (o) { o.close() });
        o = {
            id: crtid, text: $sce.trustAsHtml(text), type: type,
            close: function() {
                zone.splice((function(id){ for (var i = 0; i < zone.length; i++) if (id == zone[i].id) { return i}; return undefined;})(crtid), 1);
               },
            }
        zone.push(o);
        return o;
    }

    $scope.toggle = function(id) {
        $scope.projectName = $scope.project.name;
        $scope.projectVersion = $scope.project.release.id;
        $scope.machineName = $scope.machine.name;

        angular.element(id).toggle();
        angular.element(id+"-opposite").toggle();
    }

    $scope.selectedMostBuildTargets = function () {
        keys = Object.keys($scope.mostBuiltTargets);
        keys = keys.filter(function (e) { if ($scope.mostBuiltTargets[e]) return e });
        return keys.length == 0;

    }

    // init code
    //
    $scope.init = function() {
        $scope.pollHandle = $interval(function () { $scope._makeXHRCall({method: "GET", url: $scope.urls.xhr_edit, data: undefined});}, 4000, 0);
    }

    $scope.init();
});


/**
    TESTING CODE
*/

function test_diff_arrays() {
    _diffArrays([1,2,3], [2,3,4], function(e,f) { return e==f; }, function(e) {console.log("added", e)}, function(e) {console.log("deleted", e);})
}

var s = undefined;

function test_set_alert(text) {
    s = angular.element("div#main").scope();
    s.displayAlert(s.zone3alerts, text);
    console.log(s.zone3alerts);
    s.$digest();
}
