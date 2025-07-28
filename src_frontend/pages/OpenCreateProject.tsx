import { observer } from "mobx-react-lite";
import {useCallback} from 'react'
import {useDropzone} from 'react-dropzone'
import { GlobalStateContext } from "@/stores/globalState";
import { useContext } from "react";
import { Button } from "@/components/ui/button";
import { useState } from "react";
import { upload_file, remove_file, create_project } from "@/api/server";
import { create } from "lodash";

function OpenCreateProject() {
    const globalState = useContext(GlobalStateContext);
    const onDrop = useCallback(acceptedFiles => {
        const file_path_elements = acceptedFiles[0].path.split('/');
        if (file_path_elements[0] === "") {
            globalState.open_project(file_path_elements[1]);
        } else {
            globalState.open_project(file_path_elements[0]);
        }
        
    }, [])
    const {getRootProps, getInputProps} = useDropzone({onDrop, useFsAccessApi: false})
    const [candidateClips, setCandidateClips] = useState([]);
    const [extraScanFiles, setExtraScanFiles] = useState([]);
    const [numFrames, setNumFrames] = useState("30");
    const [frameRate, setFrameRate] = useState("10");
    const [extraFrameRate, setExtraFrameRate] = useState("2");
    const [projectName, setProjectName] = useState("");

    const handleCandidateUpload = (event) => {
        const files = Array.from(event.target.files);
        setCandidateClips((prev) => [...prev, ...files.map((file) => ({ file, start: true, end: true, all: true }))]);
        files.forEach((file) => {
            upload_file(file)
                .then((response) => {
                    console.log("File uploaded successfully:", response);
                })
                .catch((error) => {
                    console.error("Error uploading file:", error);
                });
        });
    };

    const handleExtraScanUpload = (event) => {
        const files = Array.from(event.target.files);
        setExtraScanFiles((prev) => [...prev, ...files]);
        files.forEach((file) => {
            upload_file(file)
                .then((response) => {
                    console.log("File uploaded successfully:", response);
                })
                .catch((error) => {
                    console.error("Error uploading file:", error);
                });
        });
    };

    const toggleCheckbox = (index, type) => {
        setCandidateClips((prev) =>
            prev.map((clip, i) =>
                i === index
                    ? {
                          ...clip,
                          [type]: type === "all" ? !clip.all : !clip[type],
                          ...(type === "all" ? { start: !clip.all, end: !clip.all } : {}),
                      }
                    : clip
            )
        );
    };
    
    return (
        <div className="w-full h-full flex-1 flex flex-col justify-center items-center">
            <div {...getRootProps({ className: 'dropzone' })}>
                <input {...getInputProps({ webkitdirectory: "true" })} />
                <Button variant="primary">Open Project</Button>
            </div>
            <div className="h-[50px]"></div>
            <div className="flex w-full mt-4">
                {/* Candidate Clips List */}
                <div className="w-[66%]">
                    <div className="flex-1 flex flex-col items-center">
                        <div className="flex items-center w-[180px] justify-between mb-2">
                            <h2 className="text-lg font-bold">Candidate Clips</h2>
                            <Button
                                variant="secondary"
                                className="h-8 w-8 text-sm p-0 flex items-center justify-center"
                                onClick={() => document.getElementById('candidate-upload').click()}
                            >
                                +
                            </Button>
                        </div>
                        <input
                            id="candidate-upload"
                            type="file"
                            multiple
                            className="hidden"
                            onChange={handleCandidateUpload}
                        />
                        <div className="overflow-y-auto h-80 w-full border mt-2 p-2">
                            <div className="grid grid-cols-5 gap-2 mb-1">
                                <span className="col-span-3 truncate">File Name</span>
                                <div className="flex justify-between text-center">
                                    <span className="w-full text-center">Start</span>
                                    <span className="w-full text-center">End</span>
                                    <span className="w-full text-center">All</span>
                                </div>
                                <span className="text-center">Remove File</span>
                            </div>
                            {candidateClips.map((clip, index) => (
                                <div key={index} className="grid grid-cols-5 gap-2 items-center mb-1">
                                    <span className="truncate col-span-3">{clip.file.name}</span>
                                    <div className="flex justify-between text-center">
                                        <input
                                            type="checkbox"
                                            className="mx-auto"
                                            checked={clip.start}
                                            onChange={() => toggleCheckbox(index, "start")}
                                        />
                                        <input
                                            type="checkbox"
                                            className="mx-auto"
                                            checked={clip.end}
                                            onChange={() => toggleCheckbox(index, "end")}
                                        />
                                        <input
                                            type="checkbox"
                                            className="mx-auto"
                                            checked={clip.all}
                                            onChange={() => toggleCheckbox(index, "all")}
                                        />
                                    </div>
                                    <div className="flex justify-center">
                                        <button
                                            className="text-gray-500 hover:text-gray-700 w-6 h-6 flex items-center justify-center"
                                            onClick={() => {
                                                remove_file(clip.file.name);
                                                setCandidateClips((prev) => prev.filter((_, i) => i !== index))
                                            }}
                                        >
                                            &#x2715;
                                        </button>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
                {/* Extra Scan Videos and Images List */}
                <div className="w-[33%]">
                    <div className="flex-1 flex flex-col items-center ml-4">
                        <div className="flex items-center w-[300px] justify-between mb-2">
                            <h2 className="text-lg font-bold">Extra Scan Videos and Images</h2>
                            <Button
                                variant="secondary"
                                className="h-8 w-8 text-sm p-0 flex items-center justify-center"
                                onClick={() => document.getElementById('extra-scan-upload').click()}
                            >
                                +
                            </Button>
                        </div>
                        <input
                            id="extra-scan-upload"
                            type="file"
                            multiple
                            className="hidden"
                            onChange={handleExtraScanUpload}
                        />
                        <div className="overflow-y-auto h-80 w-full border mt-2 p-2">
                            <div className="grid grid-cols-2 gap-2 mb-1 text-center">
                                <span className="truncate">File Name</span>
                                <span>Remove File</span>
                            </div>
                            {extraScanFiles.map((file, index) => (
                                <div key={index} className="grid grid-cols-2 gap-2 items-center mb-1 text-center">
                                    <span className="truncate">{file.name}</span>
                                    <button
                                        className="text-gray-500 hover:text-gray-700 w-6 h-6 flex items-center justify-center mx-auto"
                                        onClick={() =>
                                            setExtraScanFiles((prev) => prev.filter((_, i) => i !== index))
                                        }
                                    >
                                        &#x2715;
                                    </button>
                                </div>
                            ))}
                        </div>
                    </div>            
                </div>
            </div>
            {/* Text Inputs */}
            <div className="flex w-full mt-4 justify-between space-x-10">
                <div className="flex flex-row items-center space-x-2">
                    <p className="font-semibold">Project Name: </p>
                    <input
                        type="text"
                        value={projectName}
                        style={{ color: 'white', backgroundColor: '#1D1D1D', width: '300px'}}
                        onChange={(e) => setProjectName(e.target.value)}
                    />
                </div>
                <div className="flex flex-row items-center space-x-2">
                    <p className="font-semibold">Number of Frames to Extract at Start and End: </p>
                    <input
                        type="text"
                        value={numFrames}
                        style={{ color: 'white', backgroundColor: '#1D1D1D', width: '30px'}}
                        onChange={(e) => setNumFrames(e.target.value)}
                    />
                </div>
                <div className="flex flex-row items-center space-x-2">
                    <p className="font-semibold">Middle Part Extraction Rate: </p>
                    <input
                        type="text"
                        value={frameRate}
                        style={{ color: 'white', backgroundColor: '#1D1D1D', width: '30px'}}
                        onChange={(e) => setFrameRate(e.target.value)}
                    />
                </div>
                <div className="flex flex-row items-center space-x-2">
                    <p className="font-semibold">Frame Extraction Rate for Extra Scan Videos: </p>
                    <input
                        type="text"
                        value={extraFrameRate}
                        style={{ color: 'white', backgroundColor: '#1D1D1D', width: '30px'}}
                        onChange={(e) => setExtraFrameRate(e.target.value)}
                    />
                </div>
            </div>
            {/* Create Project Button */}
            <Button
                variant="primary"
                className="mt-4"
                onClick={() => {            
                    const projectData = {
                        'project_name': projectName,
                        'env_scan_files': extraScanFiles.map((file) => file.name),
                        'tbc_file_config': candidateClips
                            .filter((clip) => clip.start || clip.end || clip.all)
                            .map((clip) => ({
                                [clip.file.name]: clip.all
                                    ? ['all']
                                    : [
                                        ...(clip.start ? ['start'] : []),
                                        ...(clip.end ? ['end'] : []),
                                    ],
                            })),
                        'tbc_two_ends_num_frame': parseInt(numFrames),
                        'tbc_fps': parseFloat(frameRate),
                        'env_scan_fps': parseFloat(extraFrameRate),
                    };
                    if (projectName.trim().length === 0) {
                        alert("Project name cannot be empty.");
                        return;
                    }

                    if (candidateClips.length < 1) {
                        alert("Please upload at least two candidate clip.");
                        return;
                    }
                    
                    create_project(projectData);
                }}
            >
                Create Project
            </Button>
        </div>
    );
}

export default observer(OpenCreateProject);