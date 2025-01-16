from flask import Flask, render_template, request, redirect, url_for, send_file, session
import pandas as pd
import os
import json
import plotly.graph_objects as go
from plotly.utils import PlotlyJSONEncoder

app = Flask(__name__)
app.secret_key = 'auction_secret'

team_details = {
    "Black Panthers": {
        "color_start": "#000000",
        "color_end": "#434343",
        "logo": "/static/images/Black Panthers.png",
        "graph_color": "#FFD700"
    },
    "Red Hawks": {
        "color_start": "#FF0000",
        "color_end": "#FF5733",
        "logo": "/static/images/Red Hawks.png",
        "graph_color": "#FF4500"
    },
    "Blue Beast": {
        "color_start": "#0000FF",
        "color_end": "#1E90FF",
        "logo": "/static/images/Blue Beast.png",
        "graph_color": "#1E90FF"
    },
    "White Walkers": {
        "color_start": "#FFFFFF",
        "color_end": "#5db2ef",
        "logo": "/static/images/White Walkers.png",
        "graph_color": "#87CEEB"
    }
}


# Load the data from the uploaded Excel file
data_path = 'SOM League 25 Proficiency.xlsx'
players_df = pd.read_excel(data_path).fillna(0)  # Replace empty values with zero
players_df['Team'] = None  # Add a column to track assigned teams
players_df['Price'] = None  # Add a column to track player price

# Initialize teams
teams = {
    'Black Panthers': {"players": [], "budget": 60},
    'Red Hawks': {"players": [], "budget": 60},
    'Blue Beast': {"players": [], "budget": 60},
    'White Walkers': {"players": [], "budget": 60}
}

@app.route('/')
def home():
    global teams, players_df

    # Compute team-wise statistics
    team_stats = {}
    for team, data in teams.items():
        total_players = len(data["players"])
        total_male = sum(1 for player in data["players"] if player.get("Gender") == "Male")
        total_female = sum(1 for player in data["players"] if player.get("Gender") == "Female")
        total_batch_25 = sum(1 for player in data["players"] if player.get("Batch") == "SOM'25")
        total_batch_26 = sum(1 for player in data["players"] if player.get("Batch") == "SOM'26")

        team_stats[team] = {
            "budget": data["budget"],
            "total_players": total_players,
            "total_male": total_male,
            "total_female": total_female,
            "total_batch_25": total_batch_25,
            "total_batch_26": total_batch_26
        }

    # Compute overall statistics
    total_players = sum(stat["total_players"] for stat in team_stats.values())
    total_male = sum(stat["total_male"] for stat in team_stats.values())
    total_female = sum(stat["total_female"] for stat in team_stats.values())
    total_batch_25 = sum(stat["total_batch_25"] for stat in team_stats.values())
    total_batch_26 = sum(stat["total_batch_26"] for stat in team_stats.values())

    return render_template(
        'home.html',
        team_stats=team_stats,
        total_players=total_players,
        total_male=total_male,
        total_female=total_female,
        total_batch_25=total_batch_25,
        total_batch_26=total_batch_26
    )


@app.route('/admin', methods=['GET', 'POST'])
def admin():
    global players_df
    if 'current_player_index' not in session:
        session['current_player_index'] = 0

    if request.method == 'POST':
        if 'search' in request.form:
            search_name = request.form.get('search')
            matched_player = players_df[players_df['Name'] == search_name]
            if not matched_player.empty:
                # Convert the matched index to Python-native int before storing in session
                session['current_player_index'] = int(matched_player.index[0])

        elif 'team' in request.form:
            current_index = session['current_player_index']
            team_name = request.form.get('team')
            price = float(request.form.get('price')) if request.form.get('price') else 0.0
            image = players_df.at[current_index, 'Profile'] if 'Profile' in players_df.columns else None

            if team_name and price <= teams[team_name]["budget"]:
                # Check if the player is already assigned
                if players_df.at[current_index, 'Team'] is not None:
                    return "Player already assigned to another team.", 400

                # Deduct budget and assign player to team
                teams[team_name]["budget"] -= price
                teams[team_name]["players"].append({
                    "Name": players_df.at[current_index, 'Name'],
                    "Price": price,
                    "Image": image,
                    "Gender": players_df.at[current_index, 'Gender'],
                    "Batch": players_df.at[current_index, 'Batch']
                })

                # Update player data
                players_df.at[current_index, 'Team'] = team_name
                players_df.at[current_index, 'Price'] = price

    current_index = session.get('current_player_index', 0)

    if current_index >= len(players_df):
        return render_template('auction_end.html')

    current_player = players_df.iloc[current_index].to_dict()

    sports_columns = [col for col in players_df.columns if 'Proficiency' in col]
    renamed_columns = {col: col.replace(' - Proficiency', '') for col in sports_columns}
    player_proficiency = players_df.loc[current_index, sports_columns]
    player_proficiency.rename(index=renamed_columns, inplace=True)
    filtered_proficiency = player_proficiency[player_proficiency > 0]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=filtered_proficiency.index.tolist(),
        y=filtered_proficiency.values.tolist(),
        marker_color='skyblue',
        text=filtered_proficiency.values.tolist(),
        textposition='auto'
    ))
    fig.update_layout(
        title=f"Proficiency Across Sports for {current_player['Name']}",
        xaxis_title="Sports",
        yaxis_title="Proficiency Level",
        xaxis_tickangle=-45,
        template="simple_white",
        height=400
    )

    graph_json = json.dumps(fig, cls=PlotlyJSONEncoder)

    all_players = players_df[['Name']].to_dict(orient='records')

    return render_template(
        'admin.html', 
        player=current_player, 
        teams=teams, 
        graph_json=graph_json, 
        all_players=all_players
    )

@app.route('/end_auction')
def end_auction():
    output_path = 'auction_results.xlsx'
    players_df[['Name', 'Batch', 'Segment', 'Gender', 'Team', 'Price']].to_excel(output_path, index=False)
    return send_file(output_path, as_attachment=True)

@app.route('/spin_wheel')
def spin_wheel():
    global players_df

    # Filter for marquee players (example: 'Segment' column is 'Marquee')
    marquee_players = players_df[
        (players_df['Team'].isna()) & (players_df['Segment'] == 'Marquee')
    ]['Name'].tolist()

    # Pass the marquee player list to the spin.html template
    return render_template('spin.html', player_list=marquee_players)



@app.route('/team/<team_name>')
def team_page(team_name):
    global teams

    # Validate the team name
    if team_name not in teams:
        return "Team not found", 404

    # Retrieve team data
    team_players = teams[team_name]["players"]
    team_stats = {
        "categories": ["Total Players", "Male Players", "Female Players", "Batch 25", "Batch 26"],
        "values": [
            len(team_players),
            sum(1 for player in team_players if player.get("Gender") == "Male"),
            sum(1 for player in team_players if player.get("Gender") == "Female"),
            sum(1 for player in team_players if player.get("Batch") == "SOM'25"),
            sum(1 for player in team_players if player.get("Batch") == "SOM'26")
        ]
    }

    return render_template(
        'black_panther_page.html',
        team_players=team_players,
        team_name=team_name,
        team_stats_data=json.dumps(team_stats),
        team_color_start=team_details[team_name]['color_start'],
        team_color_end=team_details[team_name]['color_end'],
        team_logo=team_details[team_name]['logo'],
        graph_color=team_details[team_name]['graph_color']
    )

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=10000)