import os
import sys

version_map = {
    2025: 0x60,
    2024: 0x5F,
    2023: 0x5E,
    2022: 0x5D
}

reverse_map = {v: k for k, v in version_map.items()}


def downgrade_ffx(input_path, target_year=2023):

    if target_year not in version_map:
        print("Unsupported target version")
        return

    target_byte = version_map[target_year]

    try:
        with open(input_path, "rb") as f:
            data = bytearray(f.read())

        if data[0:4] != b"RIFX":
            print("Not a valid FFX file")
            return

        found = False

        for i in range(len(data)):

            if data[i] in reverse_map:
                current_year = reverse_map[data[i]]

                if current_year <= target_year:
                    continue

                print(f"Found AE {current_year} marker at offset {i}")

                data[i] = target_byte
                found = True
                break

        if not found:
            print("Could not locate version byte")
            return

        output = input_path.replace(".ffx", f"_AE{target_year}.ffx")

        with open(output, "wb") as f:
            f.write(data)

        print("Success:", output)

    except Exception as e:
        print("Error:", e)


def main():

    if len(sys.argv) < 2:
        path = input("Drop .ffx path: ").strip('"')
    else:
        path = sys.argv[1]

    downgrade_ffx(path, 2023)


if __name__ == "__main__":
    main()