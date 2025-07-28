import { observer } from "mobx-react-lite";
import { Switch } from "@/components/ui/switch";
import { getSettings, setSettings } from "@/api/server";
import { useEffect, useState } from "react";

function Setting() {
    const [colmap_bin_path, set_colmap_bin_path] = useState('');
    const [repo_path, set_repo_path] = useState('');
    const [is_on_cpu, set_is_on_cpu] = useState(false);

    useEffect(() => {
        const fetch_setting = async () => {
            const settings = await getSettings();
            console.log(settings['colmap_bin_path'])
            set_colmap_bin_path(settings['colmap_bin_path']);
            set_repo_path(settings['repo_path']);
            set_is_on_cpu(settings['data_device']==='cpu');
        }
        fetch_setting()
    }, [])

    const change_setting = (new_colmap_bin_path: string, new_repo_path: string, new_is_on_cpu: boolean) => {
        setSettings(
            new_repo_path,
            new_is_on_cpu ? 'cpu' : 'cuda',
            new_colmap_bin_path
        );
    };

    return (
        <div className="w-full h-full flex-1 flex flex-col justify-center items-center space-y-2" style={{ width: '80vw' }}>
            <div className="w-full flex space-x-2 justify-left items-center">
                <p className="font-semibold">COLMAP binary path:</p>
                <input
                    type="text"
                    value={colmap_bin_path}
                    style={{ color: 'white', backgroundColor: '#1D1D1D', flex: '1' }}
                    onChange={(event) => {
                        const value = event.target.value;
                        set_colmap_bin_path(value);
                        change_setting(value, repo_path, is_on_cpu);
                    }}
                />
            </div>
            <div className="w-full flex space-x-2 justify-left items-center">
                <p className="font-semibold">Hybrid Tours Repository Path:</p>
                <input
                    type="text"
                    value={repo_path}
                    style={{ color: 'white', backgroundColor: '#1D1D1D', flex: '1'}}
                    onChange={(event) => {
                        const value = event.target.value;
                        set_repo_path(value);
                        change_setting(colmap_bin_path, value, is_on_cpu);
                    }}
                />
            </div>
            <div className="w-full flex space-x-2 justify-left items-center">
                <p className="font-semibold">Load Training Images on CPU:</p>
                <Switch
                    checked={is_on_cpu}
                    onCheckedChange={() => {
                        const new_is_on_cpu = !is_on_cpu;
                        set_is_on_cpu(new_is_on_cpu);
                        change_setting(colmap_bin_path, repo_path, new_is_on_cpu);
                    }}
                ></Switch>
            </div>
        </div>
    )
}

export default observer(Setting);